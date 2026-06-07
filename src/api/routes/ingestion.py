import logging
import numpy as np
from fastapi import APIRouter, HTTPException, Depends
from src.api.database import get_db, ParkingLot, OccupancyRecord
from src.api.schemas import IngestOccupancyRequest, IngestOccupancyResponse, IngestSensorReadingsRequest, IngestSensorReadingsResponse
from src.api.auth import get_current_user
from src.api.utils import require_role
from src.iot.sensors import DualSensorPair

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/ingestion", tags=["Ingestion"])

@router.post("/sensor-readings", response_model=IngestSensorReadingsResponse)
async def ingest_sensor_readings(body: IngestSensorReadingsRequest, user: dict = Depends(get_current_user), db = Depends(get_db)):
    """Ingest raw dual-sensor readings through the fusion pipeline.
    
    This endpoint implements the paper's dual-sensor confirmation claim:
    ultrasonic + vision readings are fused via clean_reading() before
    producing the occupancy record, eliminating false positives from
    weather or lighting.
    """
    require_role(user, {"admin", "city_planner", "lot_owner", "sensor"})
    lot = db.query(ParkingLot).filter(ParkingLot.lot_id == body.lot_id).first()
    if not lot:
        raise HTTPException(404, f"Lot {body.lot_id} not found")

    if body.ultrasonic_readings is None or body.vision_readings is None:
        from src.pipeline.orchestrator import pipeline
        from datetime import datetime, timezone
        slot_count = body.total_slots or lot.total_slots
        simulator = pipeline._get_sensor_simulator(body.lot_id, slot_count)
        current_time = datetime.now(timezone.utc)
        sim_readings = simulator.sample_step(current_time)
        u_readings = [r.ultrasonic_occupied for r in sim_readings]
        v_readings = [r.vision_occupied for r in sim_readings]
        weather = simulator.get_weather_factor(current_time)
    else:
        if len(body.ultrasonic_readings) != len(body.vision_readings):
            raise HTTPException(400, "ultrasonic_readings and vision_readings must have the same length")
        if not body.ultrasonic_readings:
            raise HTTPException(400, "At least one sensor reading required")
        slot_count = len(body.ultrasonic_readings)
        u_readings = body.ultrasonic_readings
        v_readings = body.vision_readings
        weather = body.weather_factor if body.weather_factor is not None else 0.0

    sensor = DualSensorPair(body.lot_id, slot_count=slot_count)
    readings = sensor.fuse_raw(u_readings, v_readings)
    fused = sensor.clean_reading(readings)
    occ_rate = float(fused.mean())
    fp_rate = sensor.false_positive_rate(readings)
    latest = db.query(OccupancyRecord).filter(
        OccupancyRecord.lot_id == body.lot_id
    ).order_by(OccupancyRecord.timestamp.desc()).first()
    price = latest.price if latest else lot.base_price
    record = OccupancyRecord(
        lot_id=body.lot_id,
        occupied_slots=int(occ_rate * slot_count),
        total_slots=slot_count,
        occupancy_rate=round(occ_rate, 4),
        net_flux=body.net_flux or 0.0,
        price=price,
    )
    db.add(record)
    db.commit()
    logger.info("Fused sensor readings for lot %s: occupancy=%.1f%% fp_rate=%.2f", body.lot_id, occ_rate * 100, fp_rate)
    return IngestSensorReadingsResponse(
        status="ingested", lot_id=body.lot_id, occupancy_rate=round(occ_rate, 4),
        false_positive_rate=round(fp_rate, 4), fused_count=slot_count, weather_factor=weather,
    )

@router.post("/occupancy", response_model=IngestOccupancyResponse)
async def ingest_occupancy(report: IngestOccupancyRequest, user: dict = Depends(get_current_user), db = Depends(get_db)):
    require_role(user, {"admin", "city_planner", "lot_owner", "sensor"})
    logger.warning("event=ingestion.aggregated fusion=bypassed lot=%s — use POST /ingestion/sensor-readings for dual-sensor fusion pipeline", report.lot_id)
    try:
        lot = db.query(ParkingLot).filter(ParkingLot.lot_id == report.lot_id).first()
        if not lot:
            raise HTTPException(404, f"Lot {report.lot_id} not found")
        if user.get("role") != "admin":
            from src.api.database import User as UserModel
            caller = db.query(UserModel).filter(UserModel.email == user.get("sub")).first()
            if caller and lot.owner_id and lot.owner_id != caller.id:
                raise HTTPException(403, "You do not own this lot")
        if report.total_slots <= 0:
            raise HTTPException(400, "total_slots must be positive")
        occ_rate = round(report.occupied_slots / report.total_slots, 4)
        latest = db.query(OccupancyRecord).filter(
            OccupancyRecord.lot_id == report.lot_id
        ).order_by(OccupancyRecord.timestamp.desc()).first()
        if latest:
            price = latest.price
        else:
            price = lot.base_price
            logger.info("No prior occupancy for lot %s, using base_price=%.2f as fallback", report.lot_id, float(lot.base_price))
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
