import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from src.api.database import get_db, ParkingLot, OccupancyRecord
from src.api.schemas import IngestOccupancyRequest, IngestOccupancyResponse
from src.api.auth import get_current_user
from src.api.utils import require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/ingestion", tags=["Ingestion"])

@router.post("/occupancy", response_model=IngestOccupancyResponse)
async def ingest_occupancy(report: IngestOccupancyRequest, user: dict = Depends(get_current_user), db = Depends(get_db)):
    require_role(user, {"admin", "city_planner", "sensor"})
    try:
        lot = db.query(ParkingLot).filter(ParkingLot.lot_id == report.lot_id).first()
        if not lot:
            raise HTTPException(404, f"Lot {report.lot_id} not found")
        if user.get("role") != "admin":
            from src.api.database import User as UserModel
            caller = db.query(UserModel).filter(UserModel.email == user.get("sub")).first()
            if caller and lot.owner_id and lot.owner_id != caller.id:
                raise HTTPException(403, "You do not own this lot")
        occ_rate = round(report.occupied_slots / max(report.total_slots, 1), 4)
        latest = db.query(OccupancyRecord).filter(
            OccupancyRecord.lot_id == report.lot_id
        ).order_by(OccupancyRecord.timestamp.desc()).first()
        price = latest.price if latest else lot.base_price
        record = OccupancyRecord(
            lot_id=report.lot_id,
            occupied_slots=report.occupied_slots,
            total_slots=report.total_slots,
            occupancy_rate=occ_rate,
            net_flux=report.net_flux,
            price=price,
        )
        db.add(record)
        db.commit()
        logger.info("Ingested occupancy for lot %s: %.1f%%", report.lot_id, occ_rate * 100)
        return IngestOccupancyResponse(status="ingested", lot_id=report.lot_id, occupancy_rate=occ_rate)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Ingestion failed: %s", e)
        logger.exception("Ingestion failed")
        raise HTTPException(500, "Failed to ingest occupancy data")
