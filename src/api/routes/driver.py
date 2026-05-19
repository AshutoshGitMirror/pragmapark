from fastapi import APIRouter
from datetime import datetime
from typing import Optional

from src.api.database import get_session as db_session, ParkingLot, OccupancyRecord
from src.pipeline.orchestrator import pipeline

router = APIRouter(prefix="/api/v1/driver", tags=["driver"])

@router.get("/lots")
async def search_lots():
    db = db_session()
    try:
        lots = db.query(ParkingLot).all()
        lots_data = []
        for lot in lots:
            latest = db.query(OccupancyRecord).filter(
                OccupancyRecord.lot_id == lot.lot_id,
            ).order_by(OccupancyRecord.timestamp.desc()).first()

            lots_data.append({
                "lot_id": lot.lot_id,
                "name": lot.name,
                "address": lot.address,
                "total_slots": lot.total_slots,
                "base_price": lot.base_price,
                "current_occupancy": latest.occupancy_rate if latest else 0.3,
                "current_price": latest.price if latest else lot.base_price,
                "latitude": lot.latitude,
                "longitude": lot.longitude,
            })

        enriched = pipeline.driver_search_lots(lots_data)
        return {"lots": enriched}
    finally:
        db.close()

@router.get("/lots/{lot_id}")
async def lot_detail(lot_id: str):
    db = db_session()
    try:
        lot = db.query(ParkingLot).filter(ParkingLot.lot_id == lot_id).first()
        if not lot:
            return {"error": "not_found"}

        records = db.query(OccupancyRecord).filter(
            OccupancyRecord.lot_id == lot_id,
        ).order_by(OccupancyRecord.timestamp.desc()).limit(24).all()

        return {
            "lot_id": lot.lot_id,
            "name": lot.name,
            "address": lot.address,
            "total_slots": lot.total_slots,
            "base_price": lot.base_price,
            "latitude": lot.latitude,
            "longitude": lot.longitude,
            "recent_occupancy": [
                {"ts": r.timestamp.isoformat() if r.timestamp else None, "rate": r.occupancy_rate, "price": r.price}
                for r in records
            ],
        }
    finally:
        db.close()

@router.get("/pipeline/status")
async def pipeline_status():
    return pipeline.status()
