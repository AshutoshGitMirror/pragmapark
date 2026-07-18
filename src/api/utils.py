import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, cast
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException

from src.api.database import (
    SlotReservation,
    PrebookRecord,
    get_db_cm,
    OccupancyRecord,
    RateLimitWindow,
)
from src.micro.state_engine import slot_state_engine
from src.constants import RESERVATION_ACTIVE, RESERVATION_CONFIRMED

logger = logging.getLogger(__name__)

ADMIN_ROLES: set[str] = {"admin", "city_planner", "lot_owner"}


class RateLimiter:
    """In-memory sliding-window rate limiter (global middleware only)."""

    def __init__(
        self,
        max_calls: int = 10,
        window: float = 60.0,
        cleanup_interval: float = 600.0,
    ):
        self.max_calls = max_calls
        self.window = window
        self.cleanup_interval = cleanup_interval
        self._buckets: dict[str, list[float]] = {}
        self._last_cleanup = time.monotonic()

    def check(self, key: str) -> bool:
        now = time.monotonic()
        self._maybe_cleanup(now)
        bucket = self._buckets.get(key)
        if bucket is None:
            self._buckets[key] = [now]
            return True
        cutoff = now - self.window
        bucket[:] = [t for t in bucket if t > cutoff]
        if len(bucket) >= self.max_calls:
            return False
        bucket.append(now)
        return True

    def _maybe_cleanup(self, now: float) -> None:
        if now - self._last_cleanup > self.cleanup_interval:
            cutoff = now - self.cleanup_interval
            self._buckets = {
                k: v for k, v in self._buckets.items() if v and v[-1] >= cutoff
            }
            self._last_cleanup = now


class DBRateLimiter:
    """Database-backed rate limiter using RateLimitWindow table.

    Uses an independent DB session so that rate-limit writes are committed
    immediately — never lost by a route handler's transaction rollback.
    Survives server restarts.
    """

    def __init__(
        self, max_calls: int = 10, window: float = 60.0, prefix: str = "rl"
    ):
        self.max_calls = max_calls
        self.window = window
        self.prefix = prefix

    def check(self, key: str, db=None) -> bool:
        if db is not None:
            return self._do_check(key, db)
        from src.api.database import get_db_cm

        with get_db_cm() as cm:
            return self._do_check(key, cm)

    def _do_check(self, key: str, db) -> bool:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=self.window)
        composite = f"{self.prefix}:{key}"

        try:
            return self._try_check(composite, cutoff, now, db)
        except IntegrityError:
            db.rollback()
            # SQLite: with_for_update() is a no-op — IntegrityError means
            # two processes raced on INSERT.  Retrying makes things worse
            # (every retry also races), so deny this call.
            if db.get_bind().dialect.name == 'sqlite':
                return False
            # PostgreSQL: FOR UPDATE prevents the initial race, but a
            # UniqueViolation can still happen if two sessions both miss
            # the row.  One retry is enough — FOR UPDATE serializes.
            return self._try_check(composite, cutoff, now, db)

    def _try_check(
        self, composite: str, cutoff: datetime, now: datetime, db
    ) -> bool:
        entry = (
            db.query(RateLimitWindow)
            .filter(RateLimitWindow.key == composite)
            .with_for_update()
            .first()
        )

        if entry is not None:
            ws = entry.window_start
            if ws.tzinfo is None:
                ws = ws.replace(tzinfo=timezone.utc)
            if ws >= cutoff and entry.call_count >= self.max_calls:
                return False
            if ws >= cutoff:
                entry.call_count += 1
                db.commit()
                return True

        if entry is None:
            db.add(
                RateLimitWindow(
                    key=composite, window_start=now, call_count=1
                )
            )
        else:
            entry.window_start = now
            entry.call_count = 1
        db.commit()
        return True


class DBLock:
    """Cross-process mutex via SELECT ... FOR UPDATE on app_locks table.

    On SQLite (local dev / tests) falls back to threading.Lock because SQLite
    does not allow concurrent writers.  On PostgreSQL (production) two uvicorn
    workers can coordinate via row-level locking.

    Requires the app_locks row to be pre-seeded at startup.
    """

    def __init__(self, lock_id: int = 1):
        self._lock_id = lock_id
        self._db = None
        self._fallback = None

    def __enter__(self):
        from src.api.database import get_session, AppLock, DB_URL

        if DB_URL.startswith("sqlite"):
            import threading

            self._fallback = threading.Lock()
            self._fallback.__enter__()
            return self
        self._db = get_session()
        self._db.query(AppLock).filter(
            AppLock.id == self._lock_id
        ).with_for_update().first()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._fallback is not None:
            self._fallback.__exit__(exc_type, exc_val, exc_tb)
            self._fallback = None
        if self._db is not None:
            self._db.close()
            self._db = None


def require_role(user: dict, allowed_roles: Optional[set] = None) -> None:
    if allowed_roles is None:
        allowed_roles = ADMIN_ROLES
    if user.get("role") not in allowed_roles:
        raise HTTPException(403, "Insufficient permissions")


def require_admin(user: dict) -> None:
    require_role(user, ADMIN_ROLES)


def driver_id(user: dict) -> str:
    return user.get("sub") or user.get("email", "unknown")


# ---------------------------------------------------------------------------
# Micro slot state rehydration (singleton, extracted to avoid duplication)
# ---------------------------------------------------------------------------
def rehydrate_micro_state():
    """Restore active slot reservations AND prebooks from DB
    into the in-memory state engine."""
    try:
        with get_db_cm() as db:
            now = datetime.now(timezone.utc)

            # Restore RESERVED slots from SlotReservation
            active = (
                db.query(SlotReservation)
                .filter(
                    SlotReservation.status == RESERVATION_ACTIVE,
                    SlotReservation.expires_at > now,
                )
                .all()
            )
            recovered = 0
            for res in active:
                remaining_s = max(
                    int((res.expires_at - now).total_seconds()), 1
                )
                if slot_state_engine.reserve(
                    cast(int, res.slot_id),
                    cast(str, res.driver_id),
                    remaining_s,
                ):
                    recovered += 1
            if recovered:
                logger.info(
                    "event=rehydrate.reservations recovered=%d total=%d",
                    recovered,
                    len(active),
                )

            # Restore PREBOOKED slots from PrebookRecord
            active_prebooks = (
                db.query(PrebookRecord)
                .filter(
                    PrebookRecord.status.in_(
                        [RESERVATION_ACTIVE, RESERVATION_CONFIRMED]
                    ),
                    PrebookRecord.expires_at > now,
                )
                .all()
            )
            prebook_recovered = 0
            for pb in active_prebooks:
                target_ts = pb.target_time.timestamp()
                if slot_state_engine.prebook(
                    cast(int, pb.slot_id),
                    cast(str, pb.driver_id),
                    target_ts,
                ):
                    prebook_recovered += 1
            if prebook_recovered:
                logger.info(
                    "event=rehydrate.prebooks recovered=%d total=%d",
                    prebook_recovered,
                    len(active_prebooks),
                )
    except Exception:
        logger.exception("event=rehydrate.failed")


# ---------------------------------------------------------------------------
# CRUD helpers  (extracted from database.py to keep ORM models clean)
# ---------------------------------------------------------------------------
def get_latest_occupancies(session, lot_ids: list) -> dict:
    if not lot_ids:
        return {}
    try:
        most_recent = (
            session.query(
                OccupancyRecord.lot_id,
                func.max(OccupancyRecord.timestamp),
            )
            .filter(OccupancyRecord.lot_id.in_(lot_ids))
            .group_by(OccupancyRecord.lot_id)
            .subquery()
        )
        records = (
            session.query(OccupancyRecord)
            .join(
                most_recent,
                (OccupancyRecord.lot_id == most_recent.c[0])
                & (OccupancyRecord.timestamp == most_recent.c[1]),
            )
            .all()
        )
        return {r.lot_id: r for r in records}
    except Exception:
        logger.exception("event=occupancy.query.failed")
        return {}


def get_recent_records(session, lot_id: str, limit: int = 10) -> list:
    return (
        session.query(OccupancyRecord)
        .filter(
            OccupancyRecord.lot_id == lot_id,
        )
        .order_by(OccupancyRecord.timestamp.desc())
        .limit(limit)
        .all()
    )


def lot_to_summary(lot, latest=None) -> dict:
    return {
        "lot_id": lot.lot_id,
        "name": lot.name,
        "address": lot.address or "",
        "city": lot.city or "",
        "total_slots": lot.total_slots,
        "latitude": lot.latitude or 0.0,
        "longitude": lot.longitude or 0.0,
        "base_price": lot.base_price,
        "price_cap": lot.price_cap,
        "current_occupancy": round(latest.occupancy_rate * 100, 1)
        if (latest and latest.occupancy_rate is not None)
        else 0.0,
        "current_price": latest.price
        if (latest and latest.price is not None)
        else lot.base_price,
    }
