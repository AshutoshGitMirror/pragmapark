import hashlib, os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from src.api.database import get_session, SessionManager

router = APIRouter()

class SessionStartRequest(BaseModel):
    lot_id: str
    driver_id: str
    total_slots: int = 500
    base_price: float = 10.0

class SessionEndRequest(BaseModel):
    lot_id: str
    driver_id: str
    session_id: str
    start_time: str
    current_occupancy: float
    entry_price: float
    total_slots: int = 500

@router.post("/sessions/start")
def start_session(req: SessionStartRequest, db=Depends(get_session)):
    from src.pipeline.orchestrator import pipeline
    result = pipeline.start_session(
        lot_id=req.lot_id, driver_id=req.driver_id,
        total_slots=req.total_slots, base_price=req.base_price,
    )
    SessionManager.create_session(db, **result)
    return result

@router.post("/sessions/end")
def end_session(req: SessionEndRequest, db=Depends(get_session)):
    from src.pipeline.orchestrator import pipeline
    result = pipeline.end_session(
        session_id=req.session_id, lot_id=req.lot_id,
        driver_id=req.driver_id, start_time=req.start_time,
        current_occupancy=req.current_occupancy, entry_price=req.entry_price,
        total_slots=req.total_slots,
    )
    SessionManager.end_session(db, req.session_id, **result)
    return result

@router.get("/sessions/active")
def active_sessions(driver_id: str = None, db=Depends(get_session)):
    from src.api.database import ParkingSession
    query = db.query(ParkingSession).filter(ParkingSession.end_time.is_(None))
    if driver_id:
        query = query.filter(ParkingSession.driver_id == driver_id)
    sessions = query.order_by(ParkingSession.start_time.desc()).limit(10).all()
    return [{"session_id": s.session_id, "lot_id": s.lot_id,
             "driver_id": s.driver_id, "start_time": s.start_time.isoformat()}
            for s in sessions]
