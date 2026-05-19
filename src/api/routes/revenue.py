from fastapi import APIRouter, Depends
from datetime import datetime, timezone

from src.api.database import get_session

router = APIRouter()

@router.get("/revenue")
def get_revenue(lot_id: str = None, db=Depends(get_session)):
    from src.api.database import ParkingSession
    query = db.query(ParkingSession).filter(ParkingSession.end_time.isnot(None))
    if lot_id:
        query = query.filter(ParkingSession.lot_id == lot_id)
    sessions = query.all()
    total = sum(s.amount_charged or 0 for s in sessions)
    return {"total_revenue": round(total, 2), "completed_sessions": len(sessions)}
