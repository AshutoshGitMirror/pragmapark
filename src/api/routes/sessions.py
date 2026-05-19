from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import logging

from src.api.database import get_session as db_session, ParkingSession, ParkingLot, OccupancyRecord, PredictionMetric
from src.api.auth import get_current_user
from src.pipeline.orchestrator import pipeline
from src.features.builder import build_features_from_records

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])

class StartSessionRequest(BaseModel):
    lot_id: str = Field(min_length=1)
    slot: int = Field(default=0, ge=0)

class EndSessionRequest(BaseModel):
    session_id: str = Field(min_length=1)

def _driver_id(user: dict) -> str:
    return user.get("email") or user.get("sub", "unknown")

@router.post("/start")
async def start_session(req: StartSessionRequest, user: dict = Depends(get_current_user)):
    driver_id = _driver_id(user)
    db = db_session()
    try:
        lot = db.query(ParkingLot).filter(ParkingLot.lot_id == req.lot_id).first()
        if not lot:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Lot not found")

        records = db.query(OccupancyRecord).filter(
            OccupancyRecord.lot_id == req.lot_id,
        ).order_by(OccupancyRecord.timestamp.asc()).limit(10).all()
        features = build_features_from_records(list(records), lot.total_slots) if len(records) >= 3 else None

        result = pipeline.start_session(
            lot_id=req.lot_id,
            driver_id=driver_id,
            slot=req.slot,
            total_slots=lot.total_slots,
            base_price=lot.base_price,
            features=features,
        )

        session = ParkingSession(
            session_id=result["session_id"],
            lot_id=req.lot_id,
            driver_id=driver_id,
            slot=req.slot,
            start_time=datetime.fromisoformat(result["start_time"]),
            entry_price=result["price_at_entry"],
            status="active",
            blockchain_ref=result["blockchain_ref"],
        )
        db.add(session)

        predicted_occ = result["predicted_occupancy"]
        record = OccupancyRecord(
            lot_id=req.lot_id,
            occupied_slots=int(predicted_occ * lot.total_slots),
            total_slots=lot.total_slots,
            occupancy_rate=predicted_occ,
            price=result["price_at_entry"],
            timestamp=datetime.now(timezone.utc),
        )
        db.add(record)
        metric = PredictionMetric(
            lot_id=req.lot_id, session_id=result["session_id"],
            predicted_occupancy=predicted_occ, model_version="rf+xgb_ensemble_v2",
        )
        db.add(metric)
        db.commit()
        logger.info(f"Session {result['session_id']} started for driver {driver_id} at {req.lot_id} (pred_occ={predicted_occ:.3f})")
        return {"status": "created", "data": result}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Session start failed: {e}")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to start session")
    finally:
        db.close()

@router.post("/end")
async def end_session(req: EndSessionRequest, user: dict = Depends(get_current_user)):
    driver_id = _driver_id(user)
    db = db_session()
    try:
        sess = db.query(ParkingSession).filter(
            ParkingSession.session_id == req.session_id,
            ParkingSession.status == "active",
        ).first()
        if not sess:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Active session not found")
        if sess.driver_id != driver_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Session belongs to another driver")

        lot = db.query(ParkingLot).filter(ParkingLot.lot_id == sess.lot_id).first()
        latest = db.query(OccupancyRecord).filter(
            OccupancyRecord.lot_id == sess.lot_id,
        ).order_by(OccupancyRecord.timestamp.desc()).first()
        current_occ = latest.occupancy_rate if latest else 0.5

        result = pipeline.end_session(
            session_id=sess.session_id,
            lot_id=sess.lot_id,
            driver_id=sess.driver_id,
            start_time=sess.start_time.isoformat() if sess.start_time else datetime.now(timezone.utc).isoformat(),
            current_occupancy=current_occ,
            entry_price=sess.entry_price,
            total_slots=lot.total_slots if lot else 500,
        )

        sess.status = "completed"
        sess.end_time = datetime.fromisoformat(result["end_time"])
        sess.duration_minutes = int(result["duration_hours"] * 60)
        sess.final_price = result["final_price"]
        sess.amount_charged = result["amount_charged"]
        sess.blockchain_ref = result["blockchain_ref"]

        metric = db.query(PredictionMetric).filter(
            PredictionMetric.session_id == req.session_id,
        ).first()
        if metric and latest:
            metric.actual_occupancy = current_occ
            metric.mae = abs(metric.predicted_occupancy - current_occ)

        db.commit()
        logger.info(f"Session {req.session_id} ended, charged ${result['amount_charged']}")
        return {"status": "ended", "data": result}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Session end failed: {e}")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to end session")
    finally:
        db.close()

@router.get("/active/{lot_id}")
async def active_sessions(lot_id: str, user: dict = Depends(get_current_user)):
    db = db_session()
    try:
        sessions = db.query(ParkingSession).filter(
            ParkingSession.lot_id == lot_id,
            ParkingSession.status == "active",
        ).all()
        return {
            "lot_id": lot_id,
            "active_count": len(sessions),
            "sessions": [
                {
                    "session_id": s.session_id,
                    "slot": s.slot,
                    "start_time": s.start_time.isoformat() if s.start_time else None,
                    "entry_price": s.entry_price,
                }
                for s in sessions
            ],
        }
    finally:
        db.close()

@router.get("/history")
async def my_history(user: dict = Depends(get_current_user)):
    driver_id = _driver_id(user)
    db = db_session()
    try:
        sessions = db.query(ParkingSession).filter(
            ParkingSession.driver_id == driver_id,
        ).order_by(ParkingSession.start_time.desc()).limit(50).all()
        return {
            "total_sessions": len(sessions),
            "sessions": [
                {
                    "session_id": s.session_id,
                    "lot_id": s.lot_id,
                    "start_time": s.start_time.isoformat() if s.start_time else None,
                    "end_time": s.end_time.isoformat() if s.end_time else None,
                    "duration_minutes": s.duration_minutes,
                    "amount_charged": s.amount_charged,
                    "status": s.status,
                }
                for s in sessions
            ],
        }
    finally:
        db.close()
