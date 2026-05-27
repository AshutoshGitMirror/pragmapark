import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.api.database import get_session as db_session, ParkingSession, ParkingLot, PredictionMetric, get_recent_records
from src.features.builder import build_features_from_records
from src.pipeline.orchestrator import pipeline
from src.constants import SESSION_STALE_HOURS, MIN_RECORDS_FOR_FEATURES, DEFAULT_TOTAL_SLOTS, DEFAULT_PRICE_CAP

logger = logging.getLogger(__name__)


def create_session(lot_id: str, slot: int, driver_id: str,
                   payment_method: Optional[str] = None,
                   flat_rate: bool = False,
                   model_version: str = "rf+xgb_ensemble_v2",
                   force: bool = False) -> dict:
    db = db_session()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=SESSION_STALE_HOURS)
        db.query(ParkingSession).filter(
            ParkingSession.driver_id == driver_id,
            ParkingSession.status == "active",
            ParkingSession.start_time < cutoff,
        ).update({"status": "expired", "end_time": datetime.now(timezone.utc)})

        existing = db.query(ParkingSession).filter(
            ParkingSession.driver_id == driver_id, ParkingSession.status == "active",
        ).first()
        if existing:
            if force:
                existing.status = "expired"
                existing.end_time = datetime.now(timezone.utc)
                db.commit()
            else:
                raise RuntimeError("driver already has an active session")

        lot = db.query(ParkingLot).filter(ParkingLot.lot_id == lot_id).first()
        if not lot:
            raise RuntimeError("lot not found")

        records = get_recent_records(db, lot_id, limit=10)
        features = build_features_from_records(list(records), lot.total_slots) if len(records) >= MIN_RECORDS_FOR_FEATURES else None
        latest_occ = records[-1] if records else None

        result = pipeline.start_session(
            lot_id=lot_id, driver_id=driver_id, slot=slot,
            total_slots=lot.total_slots, base_price=lot.base_price,
            current_price=latest_occ.price if latest_occ else lot.base_price,
            price_cap=lot.price_cap, features=features,
        )

        entry_price = result["price_at_entry"]
        if flat_rate:
            entry_price = lot.base_price

        db.add(ParkingSession(
            session_id=result["session_id"], lot_id=lot_id, driver_id=driver_id,
            slot=slot, start_time=datetime.fromisoformat(result["start_time"]),
            entry_price=entry_price, status="active",
            blockchain_ref=result["blockchain_ref"],
            payment_method=payment_method,
        ))
        db.add(PredictionMetric(
            lot_id=lot_id, session_id=result["session_id"],
            predicted_occupancy=result["predicted_occupancy"], model_version=model_version,
        ))
        from src.api.ledger_outbox import enqueue_outbox, process_pending
        enqueue_outbox(db, {"type": "session_start", "session_id": result["session_id"],
                            "lot_id": lot_id, "driver_id": driver_id, "action": "park",
                            "price_at_entry": result["price_at_entry"], "ipfs_cid": result["blockchain_ref"]})
        db.commit()
        process_pending(db, pipeline)
        logger.info("Session %s started for driver %s at %s (pred_occ=%.3f)",
                     result["session_id"], driver_id, lot_id, result.get("predicted_occupancy", 0))
        return {**result, "price_at_entry": entry_price}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
