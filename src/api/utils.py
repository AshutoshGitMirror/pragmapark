from typing import Optional
import time
from fastapi import HTTPException

ADMIN_ROLES: set[str] = {"admin", "city_planner"}


class RateLimiter:
    def __init__(self, max_calls: int = 10, window: float = 60.0, cleanup_interval: float = 600.0):
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
            self._buckets = {k: v for k, v in self._buckets.items() if v and v[-1] >= cutoff}
            self._last_cleanup = now


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
    """Restore active slot reservations from DB into the in-memory state engine."""
    try:
        from typing import cast
        from src.api.database import SlotReservation, get_db_cm
        from src.micro.state_engine import slot_state_engine
        from src.constants import RESERVATION_ACTIVE
        from datetime import datetime, timezone

        with get_db_cm() as db:
            now = datetime.now(timezone.utc)
            active = db.query(SlotReservation).filter(
                SlotReservation.status == RESERVATION_ACTIVE,
                SlotReservation.expires_at > now,
            ).all()
            recovered = 0
            for res in active:
                remaining_s = max(int((res.expires_at - now).total_seconds()), 1)
                if slot_state_engine.reserve(cast(int, res.slot_id), cast(str, res.driver_id), remaining_s):
                    recovered += 1
            if recovered:
                import logging
                logging.getLogger(__name__).info(
                    "event=rehydrate recovered=%d total=%d", recovered, len(active)
                )
    except Exception:
        import logging
        logging.getLogger(__name__).exception("event=rehydrate.failed")


# ---------------------------------------------------------------------------
# CRUD helpers  (extracted from database.py to keep ORM models clean)
# ---------------------------------------------------------------------------
def get_latest_occupancies(session, lot_ids: list) -> dict:
    if not lot_ids:
        return {}
    try:
        from src.api.database import OccupancyRecord
        from sqlalchemy import func
        most_recent = session.query(
            OccupancyRecord.lot_id, func.max(OccupancyRecord.timestamp),
        ).filter(OccupancyRecord.lot_id.in_(lot_ids)).group_by(OccupancyRecord.lot_id).subquery()
        records = session.query(OccupancyRecord).join(
            most_recent,
            (OccupancyRecord.lot_id == most_recent.c[0]) &
            (OccupancyRecord.timestamp == most_recent.c[1]),
        ).all()
        return {r.lot_id: r for r in records}
    except Exception:
        return {}


def get_recent_records(session, lot_id: str, limit: int = 10) -> list:
    from src.api.database import OccupancyRecord
    return session.query(OccupancyRecord).filter(
        OccupancyRecord.lot_id == lot_id,
    ).order_by(OccupancyRecord.timestamp.desc()).limit(limit).all()


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
        "current_occupancy": latest.occupancy_rate if latest else 0,
        "current_price": latest.price if latest else lot.base_price,
    }
