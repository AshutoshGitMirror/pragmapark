from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from src.api.database import get_session, ParkingLot, OccupancyRecord, User
from src.api.auth import get_current_user

router = APIRouter(prefix="/api/v1/lots", tags=["Parking Lots"])

class LotCreate(BaseModel):
    lot_id: str = Field(min_length=1, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=255)
    address: str = ""
    total_slots: int = Field(ge=1, le=100000)
    latitude: float = 0.0
    longitude: float = 0.0
    base_price: float = Field(ge=0, le=1000)

class LotUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    total_slots: Optional[int] = None
    base_price: Optional[float] = None

@router.get("")
async def list_lots():
    session = get_session()
    try:
        lots = session.query(ParkingLot).all()
        result = []
        for lot in lots:
            latest = session.query(OccupancyRecord).filter(
                OccupancyRecord.lot_id == lot.lot_id
            ).order_by(OccupancyRecord.timestamp.desc()).first()
            result.append({
                "lot_id": lot.lot_id,
                "name": lot.name,
                "address": lot.address,
                "total_slots": lot.total_slots,
                "latitude": lot.latitude,
                "longitude": lot.longitude,
                "base_price": lot.base_price,
                "current_occupancy": latest.occupancy_rate if latest else 0,
                "current_price": latest.price if latest else lot.base_price,
            })
        return result
    finally:
        session.close()

@router.post("")
async def create_lot(lot: LotCreate, user=Depends(get_current_user)):
    session = get_session()
    try:
        existing = session.query(ParkingLot).filter(ParkingLot.lot_id == lot.lot_id).first()
        if existing:
            raise HTTPException(400, "Lot ID already exists")
        email = user.get("sub")
        if not email:
            raise HTTPException(401, "Invalid token: missing subject")
        db_user = session.query(User).filter(User.email == email).first()
        db_lot = ParkingLot(
            lot_id=lot.lot_id, name=lot.name, address=lot.address,
            total_slots=lot.total_slots, latitude=lot.latitude,
            longitude=lot.longitude, base_price=lot.base_price,
            owner_id=db_user.id,
        )
        session.add(db_lot)
        session.commit()
        return {"status": "created", "lot_id": lot.lot_id}
    finally:
        session.close()

@router.get("/{lot_id}")
async def get_lot(lot_id: str):
    session = get_session()
    try:
        lot = session.query(ParkingLot).filter(ParkingLot.lot_id == lot_id).first()
        if not lot:
            raise HTTPException(404, "Lot not found")
        records = session.query(OccupancyRecord).filter(
            OccupancyRecord.lot_id == lot_id
        ).order_by(OccupancyRecord.timestamp.desc()).limit(100).all()
        return {
            "lot_id": lot.lot_id,
            "name": lot.name,
            "address": lot.address,
            "total_slots": lot.total_slots,
            "latitude": lot.latitude,
            "longitude": lot.longitude,
            "base_price": lot.base_price,
            "history": [
                {"timestamp": r.timestamp.isoformat(), "occupancy_rate": r.occupancy_rate,
                 "price": r.price, "net_flux": r.net_flux}
                for r in reversed(records)
            ],
        }
    finally:
        session.close()

@router.get("/{lot_id}/occupancy")
async def get_occupancy(lot_id: str, hours: int = Query(24, ge=1, le=168, description="Hours of history")):
    session = get_session()
    try:
        lot = session.query(ParkingLot).filter(ParkingLot.lot_id == lot_id).first()
        if not lot:
            raise HTTPException(404, "Lot not found")
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        records = session.query(OccupancyRecord).filter(
            OccupancyRecord.lot_id == lot_id,
            OccupancyRecord.timestamp >= cutoff,
        ).order_by(OccupancyRecord.timestamp).all()
        return {
            "lot_id": lot_id,
            "name": lot.name,
            "current_occupancy": records[-1].occupancy_rate if records else 0,
            "current_price": records[-1].price if records else lot.base_price,
            "records": [
                {"timestamp": r.timestamp.isoformat(), "occupancy_rate": r.occupancy_rate,
                 "price": r.price, "net_flux": r.net_flux}
                for r in records
            ],
        }
    finally:
        session.close()
