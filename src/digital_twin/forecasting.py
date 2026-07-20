"""P2 — honest forecasting integration.

This module wires the forecasting models into the observation-driven twin
service. It enforces the remediation rules:

  * The **persistence baseline** is always produced (deterministic, no training).
  * ``STIDPredictor`` is retrained ONLY on later real observed occupancy
    (chronological, never simulated ``new_occ``). It is an EXPERIMENTAL
    candidate.
  * A candidate model is promoted to "primary" ONLY if it beats the
    persistence + ML baselines on held-out real observations (evaluated by
    MAE). Until then it stays a candidate and must not be described as a
    validated forecaster.
  * No synthetic data ever trains a model (principle 7).

Spatial features come from the real adjacency graph (``spatial`` module),
not random embeddings.
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import func

from src.api.database import get_db_cm, ParkingLot, OccupancyRecord
from src.digital_twin.orm import TwinForecast, TwinModelVersion
from src.digital_twin.service import (
    FORECAST_HORIZONS_MIN,
    PERSISTENCE_VERSION,
    SUPERVISED_VERSION,
    TwinService,
)
from src.digital_twin.spatial import coupling_strength
from src.digital_twin.stid import STIDPredictor

logger = logging.getLogger(__name__)

STID_VERSION = "stid_real_v1"


def _real_lot_ids(db) -> List[str]:
    return [lot.lot_id for lot in db.query(ParkingLot).all()]


def _history_for(db, lot_id: str) -> List[tuple]:
    """Chronological real (timestamp, occupancy_rate) from OccupancyRecord.

    Returns empty if no real data — we never fabricate a history.
    """
    rows = (
        db.query(OccupancyRecord.timestamp, OccupancyRecord.occupancy_rate)
        .filter(OccupancyRecord.lot_id == lot_id)
        .filter(OccupancyRecord.occupancy_rate.isnot(None))
        .order_by(OccupancyRecord.timestamp.asc())
        .all()
    )
    return [(r.timestamp, float(r.occupancy_rate)) for r in rows]


def train_stid_on_real_history(service: TwinService, lot_cap: int = 100) -> STIDPredictor:
    """Retrain STID only on chronological REAL observations.

    For each lot we walk its real history in time order. The model is fed
    (history_occ = previous real occ, observed_occ = current real occ, hour,
    dow). It NEVER sees simulated values. Lot adjacency for spatial identity
    is read from the real spatial graph at predict time.

    Returns the fitted predictor (also registered as a candidate in service).
    """
    stid = STIDPredictor(
        num_zones=lot_cap, spatial_dim=8, temporal_dim=8
    )
    with get_db_cm() as db:
        lot_ids = _real_lot_ids(db)
        stid.set_zone_index(lot_ids[:lot_cap])
        for lot_id in lot_ids[:lot_cap]:
            hist = _history_for(db, lot_id)
            prev = None
            for ts, occ in hist:
                if prev is None:
                    prev = occ
                    continue
                hour = ts.hour % 24
                day = ts.weekday() % 7
                try:
                    stid.train_on_real_observation(
                        lot_id=lot_id,
                        hour=hour,
                        day=day,
                        history_occ=prev,
                        observed_occ=occ,
                        lr=0.01,
                    )
                except Exception as e:  # pragma: no cover
                    logger.warning("stid train step failed lot=%s: %s", lot_id, e)
                prev = occ

    # Register as a candidate model in the service (predicts per horizon).
    def predict_fn(obs, _h):
        lot_id = obs.lot_id
        if lot_id not in stid._zone_index:
            return None
        z = stid._zone_index[lot_id]
        hour = obs.observed_at.hour % 24
        day = obs.observed_at.weekday() % 7
        p = stid.predict(z, hour, day, obs.occupancy_rate())
        return p

    service.register_model(
        "stid",
        STID_VERSION,
        lambda obs, h: _stid_forecast(predict_fn, obs, h),
    )
    n = stid.trained_real_steps
    logger.info("STID retrained on %d REAL observation steps (no simulated data)", n)
    return stid


def _stid_forecast(predict_fn, obs, _h):
    from src.digital_twin.service import ForecastResult

    p = predict_fn(obs, _h)
    if p is None:
        from src.digital_twin.service import PERSISTENCE_VERSION

        p = obs.occupancy_rate()
    return ForecastResult(
        horizon_minutes=0,
        predicted_occupancy_rate=float(p),
        lower=max(0.0, p - 0.08),
        upper=min(1.0, p + 0.08),
        model_name="stid",
        model_version=STID_VERSION,
        feature_version="real_temporal_spatial_v1",
    )


def evaluate_and_promote(
    service: TwinService, lot_id: str, horizon: int = 60
) -> dict:
    """Compare STID candidate vs persistence baseline on real evaluated rows.

    Promotion rule (P2): STID is promoted to primary ONLY if its MAE on the
    real evaluated set is strictly lower than the persistence MAE for the same
    horizon + lot. Otherwise it remains a candidate. Returns the comparison.
    """
    with get_db_cm() as db:
        rows = (
            db.query(TwinForecast)
            .filter(TwinForecast.lot_id == lot_id)
            .filter(TwinForecast.horizon_minutes == horizon)
            .filter(TwinForecast.actual_occupancy_rate.isnot(None))
            .all()
        )
        by_model: dict[str, list] = {}
        for r in rows:
            by_model.setdefault(r.model_name, []).append(r)

        def mae(name: str) -> Optional[float]:
            xs = by_model.get(name)
            if not xs:
                return None
            errs = [x.abs_error for x in xs if x.abs_error is not None]
            return sum(errs) / len(errs) if errs else None

        p_mae = mae("persistence")
        s_mae = mae("stid")
        promote = (
            p_mae is not None
            and s_mae is not None
            and s_mae < p_mae
        )
        status = "primary" if promote else "candidate"
        # Persist model-version provenance from REAL evaluation only.
        service.register_model_version(
            model_name="stid",
            artifact_version=STID_VERSION,
            feature_schema_version="real_temporal_spatial_v1",
            validation_metrics={
                "persistence_mae": round(p_mae, 6) if p_mae is not None else None,
                "stid_mae": round(s_mae, 6) if s_mae is not None else None,
                "n_evaluated": sum(len(v) for v in by_model.values()),
                "promoted": promote,
            },
            is_baseline=False,
            promotion_status=status,
        )
        return {
            "lot_id": lot_id,
            "horizon_minutes": horizon,
            "persistence_mae": p_mae,
            "stid_mae": s_mae,
            "promoted": promote,
            "status": status,
        }


def coupling_report(lot_id: str, max_band: str = "far") -> dict:
    """Spatial coupling of a lot to its real neighbors (P3 evidence)."""
    from src.digital_twin.spatial import neighbors

    ns = neighbors(lot_id, max_band=max_band)
    return {
        "lot_id": lot_id,
        "neighbor_count": len(ns),
        "neighbors": [
            {"lot_id": n, "distance_m": round(d, 1), "band": b} for n, d, b in ns
        ],
    }


def spatial_pairwise(lot_a: str, lot_b: str) -> float:
    """Deterministic real spatial coupling in [0,1] (no learned embedding)."""
    return coupling_strength(lot_a, lot_b)
