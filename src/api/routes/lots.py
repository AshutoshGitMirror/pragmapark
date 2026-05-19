from fastapi import APIRouter, Query
from datetime import datetime, timezone

from src.api.database import get_session

router = APIRouter()

@router.get("/lots")
def list_lots(db=Depends(get_session)):
    from src.api.database import ParkingLot
    lots = db.query(ParkingLot).all()
    return [{"lot_id": l.lot_id, "name": l.name, "address": l.address or "",
             "total_slots": l.total_slots, "base_price": l.base_price}
            for l in lots]

@router.get("/lots/{lot_id}/availability")
def lot_availability(lot_id: str, db=Depends(get_session)):
    from src.api.database import ParkingSession
    active = db.query(ParkingSession).filter(
        ParkingSession.lot_id == lot_id,
        ParkingSession.end_time.is_(None),
    ).count()
    lot = db.query(ParkingLot).filter(ParkingLot.lot_id == lot_id).first()
    if not lot:
        return {"lot_id": lot_id, "error": "not found"}
    available = max(lot.total_slots - active, 0)
    return {"lot_id": lot_id, "total_slots": lot.total_slots,
            "occupied": active, "available": available}
