import logging
from fastapi import APIRouter, HTTPException, Depends, Query, Path

from datetime import datetime, timezone
from typing import List
from src.api.database import get_db, ParkingLot, OccupancyRecord, User, ParkingSession
from src.constants import SESSION_RUNNING
from src.api.auth import get_current_user
from src.api.utils import require_admin, get_latest_occupancies, lot_to_summary
from src.api.schemas import LotCreate, LotUpdate, LotCreateResponse, LotUpdateResponse, LotSummary, LotDetail, LotOccupancyResponse, OccupancyHistoryItem

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/lots", tags=["Parking Lots"])

@router.get("", response_model=List[LotSummary])
async def list_lots(city: str = Query(None, description="Filter by city"),
                    offset: int = Query(0, ge=0, description="Number of records to skip"),
                    limit: int = Query(100, ge=1, le=1000, description="Max records to return"),
                    user: dict = Depends(get_current_user),
                    session = Depends(get_db)):
    q = session.query(ParkingLot)
    if city:
        q = q.filter(ParkingLot.city == city)
    q = q.order_by(ParkingLot.lot_id).offset(offset).limit(limit)
    lots = q.all()
    lot_ids = [lot.lot_id for lot in lots]
    latest_map = get_latest_occupancies(session, lot_ids) if lot_ids else {}
    result = [lot_to_summary(lot, latest_map.get(lot.lot_id)) for lot in lots]
    return result

@router.post("", response_model=LotCreateResponse)
async def create_lot(lot: LotCreate, user: dict = Depends(get_current_user), session = Depends(get_db)):
    require_admin(user)
    try:
        existing = session.query(ParkingLot).filter(ParkingLot.lot_id == lot.lot_id).first()
        if existing:
            raise HTTPException(400, "Lot ID already exists")
        email = user.get("sub")
        if not email:
            raise HTTPException(401, "Invalid token: missing subject")
        db_user = session.query(User).filter(User.email == email).first()
        if not db_user:
            raise HTTPException(401, "User not found")
        db_lot = ParkingLot(
            lot_id=lot.lot_id, name=lot.name, address=lot.address, city=lot.city,
            total_slots=lot.total_slots, latitude=lot.latitude,
            longitude=lot.longitude, base_price=lot.base_price,
            price_cap=lot.price_cap, owner_id=db_user.id,
        )
        session.add(db_lot)
        session.commit()
        return LotCreateResponse(status="created", lot_id=lot.lot_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create lot %s: %s", lot.lot_id, e)
        logger.exception("Failed to create lot %s", lot.lot_id)
        session.rollback()
        raise HTTPException(500, "Lot creation failed")


@router.get("/owner", response_model=List[LotSummary])
async def list_owner_lots(offset: int = Query(0, ge=0, description="Number of records to skip"),
                          limit: int = Query(100, ge=1, le=1000, description="Max records to return"),
                          user: dict = Depends(get_current_user),
                          session = Depends(get_db)):
    email = user.get("sub")
    if not email:
        raise HTTPException(401, "Invalid token")
    db_user = session.query(User).filter(User.email == email).first()
    if not db_user:
        raise HTTPException(404, "User not found")
    if db_user.role == "admin":
        q = session.query(ParkingLot)
    else:
        q = session.query(ParkingLot).filter(ParkingLot.owner_id == db_user.id)
    q = q.offset(offset).limit(limit)
    lots = q.all()
    lot_ids = [lot.lot_id for lot in lots]
    latest_map = get_latest_occupancies(session, lot_ids) if lot_ids else {}
    result = [lot_to_summary(lot, latest_map.get(lot.lot_id)) for lot in lots]
    return result

@router.put("/{lot_id}/config", response_model=LotUpdateResponse)
async def update_lot_config(cfg: LotUpdate, lot_id: str = Path(..., pattern=r"^[a-zA-Z0-9_-]{1,50}$"), user: dict = Depends(get_current_user), session = Depends(get_db)):
    try:
        email = user.get("sub")
        if not email:
            raise HTTPException(401, "Invalid token")
        db_user = session.query(User).filter(User.email == email).first()
        if not db_user:
            raise HTTPException(401, "User not found")
        lot = session.query(ParkingLot).filter(ParkingLot.lot_id == lot_id).first()
        if not lot:
            raise HTTPException(404, "Lot not found")
        if lot.owner_id != db_user.id and db_user.role != "admin":
            raise HTTPException(403, "Only the lot owner can update config")
        if cfg.price_cap is not None:
            lot.price_cap = cfg.price_cap
        if cfg.base_price is not None:
            lot.base_price = cfg.base_price
        if cfg.name is not None:
            lot.name = cfg.name
        if cfg.address is not None:
            lot.address = cfg.address
        if cfg.total_slots is not None:
            if cfg.total_slots < lot.total_slots:
                invalid_sessions = session.query(ParkingSession).filter(
                    ParkingSession.lot_id == lot_id,
                    ParkingSession.status == SESSION_RUNNING,
                    ParkingSession.slot >= cfg.total_slots,
                ).count()
                if invalid_sessions:
                    logger.warning(
                        "Reducing total_slots for lot %s from %d to %d leaves %d active sessions in invalid slots",
                        lot_id, lot.total_slots, cfg.total_slots, invalid_sessions,
                    )
            lot.total_slots = cfg.total_slots
        session.commit()
        return LotUpdateResponse(status="updated", lot_id=lot_id,
                base_price=lot.base_price, price_cap=lot.price_cap)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update lot %s: %s", lot_id, e)
        logger.exception("Failed to update lot %s", lot_id)
        session.rollback()
        raise HTTPException(500, "Lot update failed")

@router.get("/{lot_id}", response_model=LotDetail)
async def get_lot(lot_id: str = Path(..., pattern=r"^[a-zA-Z0-9_-]{1,50}$"),
                  user: dict = Depends(get_current_user),
                  session = Depends(get_db)):
    lot = session.query(ParkingLot).filter(ParkingLot.lot_id == lot_id).first()
    if not lot:
        raise HTTPException(404, "Lot not found")
    records = session.query(OccupancyRecord).filter(
        OccupancyRecord.lot_id == lot_id
    ).order_by(OccupancyRecord.timestamp.desc()).limit(100).all()
    return LotDetail(
        lot_id=lot.lot_id,
        name=lot.name,
        address=lot.address,
        city=lot.city,
        total_slots=lot.total_slots,
        latitude=lot.latitude,
        longitude=lot.longitude,
        base_price=lot.base_price,
        price_cap=lot.price_cap,
        history=[
            OccupancyHistoryItem(
                timestamp=r.timestamp.isoformat(), occupancy_rate=r.occupancy_rate,
                price=r.price, net_flux=r.net_flux,
            )
            for r in reversed(records)
        ],
    )

@router.get("/{lot_id}/occupancy", response_model=LotOccupancyResponse)
async def get_occupancy(lot_id: str = Path(..., pattern=r"^[a-zA-Z0-9_-]{1,50}$"),
                        hours: int = Query(24, ge=1, le=168, description="Hours of history"),
                        offset: int = Query(0, ge=0, description="Records to skip"),
                        limit: int = Query(100, ge=1, le=1000, description="Max records"),
                        user: dict = Depends(get_current_user),
                        session = Depends(get_db)):
    lot = session.query(ParkingLot).filter(ParkingLot.lot_id == lot_id).first()
    if not lot:
        raise HTTPException(404, "Lot not found")
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    latest = session.query(OccupancyRecord).filter(
        OccupancyRecord.lot_id == lot_id,
    ).order_by(OccupancyRecord.timestamp.desc()).first()
    records = session.query(OccupancyRecord).filter(
        OccupancyRecord.lot_id == lot_id,
        OccupancyRecord.timestamp >= cutoff,
    ).order_by(OccupancyRecord.timestamp).offset(offset).limit(limit).all()
    return LotOccupancyResponse(
        lot_id=lot_id,
        name=lot.name,
        current_occupancy=latest.occupancy_rate if latest else 0,
        current_price=latest.price if latest else lot.base_price,
        records=[
            OccupancyHistoryItem(
                timestamp=r.timestamp.isoformat(), occupancy_rate=r.occupancy_rate,
                price=r.price, net_flux=r.net_flux,
            )
            for r in records
        ],
    )
