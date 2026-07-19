"""Phase 3 — real residential availability model.

Replaces the Phase-1 time-of-day stub with a model learned from *observed
signals* (no hardcoded schedule):

  * Beta-Binomial estimator keyed by **neighborhood spatial bucket + (weekday,
    hour)**, so sparse standalone home slots pool signal from nearby slots.
  * Trained from ``SlotStateLog`` occupancy transitions for residential slots
    (standalone home slots + active permitted lot-attached slots).
  * Instantaneous modulation: an active share listing raises availability; a
    current booking / occupancy lowers it.
  * Persisted to ``data/residential_availability_model.json`` and lazy-trained
    from the DB on first use, so it improves as data accumulates.
"""
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from src.residential.geo import geohash_encode

logger = logging.getLogger(__name__)

MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "residential_availability_model.json",
)
# Coarser geohash for neighborhood pooling (~1.2 km buckets at precision 6).
NEIGHBORHOOD_PRECISION = 6
_ALPHA_PRIOR = 2.0
_BETA_PRIOR = 2.0


def _neighborhood_bucket(
    lat: float, lng: float, precision: int = NEIGHBORHOOD_PRECISION
) -> str:
    return geohash_encode(lat, lng, precision)


class ResidentialAvailabilityModel:
    def __init__(self) -> None:
        # (bucket, weekday, hour) -> [alpha, beta]
        self._cells: Dict[Tuple[str, int, int], List[float]] = {}
        # bucket -> [alpha, beta]  (neighborhood-level fallback)
        self._bucket: Dict[str, List[float]] = {}
        self._global: List[float] = [_ALPHA_PRIOR, _BETA_PRIOR]
        self._n_records: int = 0
        self._trained_at: Optional[str] = None
        self._loaded: bool = False

    # ── training (pure, testable without a DB) ───────────────────────────
    def train_from_records(
        self, records: List[Tuple[str, int, int, bool]]
    ) -> None:
        """``records`` = list of ``(bucket, weekday, hour, is_occupied)``."""
        cells: Dict[Tuple[str, int, int], List[float]] = {}
        bucket: Dict[str, List[float]] = {}
        a_glob = _ALPHA_PRIOR
        b_glob = _BETA_PRIOR
        for bucket_id, wd, hb, occupied in records:
            ckey = (bucket_id, wd, hb)
            cell = cells.get(ckey, [_ALPHA_PRIOR, _BETA_PRIOR])
            bk = bucket.get(bucket_id, [_ALPHA_PRIOR, _BETA_PRIOR])
            if occupied:
                cell[1] += 1.0
                bk[1] += 1.0
                b_glob += 1.0
            else:
                cell[0] += 1.0
                bk[0] += 1.0
                a_glob += 1.0
            cells[ckey] = cell
            bucket[bucket_id] = bk
        self._cells = cells
        self._bucket = bucket
        self._global = [a_glob, b_glob]
        self._n_records = len(records)
        self._trained_at = datetime.now(timezone.utc).isoformat()
        self._loaded = True

    def train_from_db(self, session) -> int:
        from src.api.database import MicroSlot, SlotStateLog

        slots = (
            session.query(MicroSlot)
            .filter((MicroSlot.lot_id.is_(None)) | (MicroSlot.active == 1))
            .all()
        )
        slots = [s for s in slots if s.latitude is not None and s.longitude is not None]
        if not slots:
            return 0
        coord = {s.id: (float(s.latitude), float(s.longitude)) for s in slots}
        logs = (
            session.query(SlotStateLog)
            .filter(SlotStateLog.slot_id.in_([s.id for s in slots]))
            .all()
        )
        records: List[Tuple[str, int, int, bool]] = []
        for r in logs:
            latlng = coord.get(r.slot_id)
            if not latlng or r.timestamp is None:
                continue
            bucket = _neighborhood_bucket(latlng[0], latlng[1])
            records.append(
                (bucket, r.timestamp.weekday(), r.timestamp.hour, r.new_state == "occupied")
            )
        if not records:
            return 0
        self.train_from_records(records)
        self.save()
        return len(records)

    # ── persistence ────────────────────────────────────────────────────────
    def save(self, path: str = MODEL_PATH) -> None:
        try:
            payload = {
                "cells": {
                    f"{k[0]}|{k[1]}|{k[2]}": v for k, v in self._cells.items()
                },
                "buckets": self._bucket,
                "global": self._global,
                "n_records": self._n_records,
                "trained_at": self._trained_at,
            }
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                json.dump(payload, f)
        except Exception as e:  # pragma: no cover - best-effort persistence
            logger.warning("Failed to save residential availability model: %s", e)

    def load(self, path: str = MODEL_PATH) -> bool:
        try:
            if not os.path.exists(path):
                return False
            with open(path) as f:
                data = json.load(f)
            self._cells = {}
            for k, v in data.get("cells", {}).items():
                b, wd, hb = k.split("|")
                self._cells[(b, int(wd), int(hb))] = v
            self._bucket = {b: v for b, v in data.get("buckets", {}).items()}
            self._global = data.get("global", [_ALPHA_PRIOR, _BETA_PRIOR])
            self._n_records = data.get("n_records", 0)
            self._trained_at = data.get("trained_at")
            self._loaded = True
            return True
        except Exception as e:  # pragma: no cover
            logger.warning("Failed to load residential availability model: %s", e)
            return False

    def ensure_loaded(self, session=None, path: str = MODEL_PATH) -> None:
        if self._loaded:
            return
        if self.load(path):
            return
        if session is not None:
            try:
                if self.train_from_db(session):
                    return
            except Exception as e:  # pragma: no cover
                logger.warning("Lazy residential model train failed: %s", e)
        # Untrained: neutral prior so predictions stay well-defined.
        self._loaded = True

    # ── prediction ─────────────────────────────────────────────────────────
    def _base_rate(self, bucket: str, dt: datetime) -> float:
        cell = self._cells.get((bucket, dt.weekday(), dt.hour))
        if cell:
            a, b = cell
        else:
            bk = self._bucket.get(bucket)
            a, b = bk if bk else self._global
        return a / (a + b) if (a + b) > 0 else 0.5

    def predict(
        self,
        lat: float,
        lng: float,
        dt: Optional[datetime] = None,
        occupied_now: Optional[bool] = None,
        has_active_share: bool = False,
        has_booking_at: bool = False,
        session=None,
    ) -> Dict[str, object]:
        self.ensure_loaded(session=session)
        dt = dt or datetime.now(timezone.utc)
        bucket = _neighborhood_bucket(lat, lng)

        if occupied_now is True:
            base_now = 0.05
        else:
            base_now = self._base_rate(bucket, dt)
            if has_active_share:
                base_now = max(base_now, 0.6)

        p15 = self._base_rate(bucket, dt + timedelta(minutes=15))
        p60 = self._base_rate(bucket, dt + timedelta(minutes=60))
        if has_active_share:
            p15, p60 = max(p15, 0.6), max(p60, 0.6)
        if has_booking_at:
            p15, p60 = min(p15, 0.15), min(p60, 0.15)

        return {
            "p_available_now": round(min(1.0, max(0.0, base_now)), 3),
            "p_available_15m": round(min(1.0, max(0.0, p15)), 3),
            "p_available_60m": round(min(1.0, max(0.0, p60)), 3),
            "model": "residential_beta_binomial",
            "trained_at": self._trained_at,
        }


residential_availability_model = ResidentialAvailabilityModel()
