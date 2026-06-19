from datetime import timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from typing import Optional

from src.api.database import get_db, ParkingLot, OccupancyRecord, MicroSlot
from src.api.auth import get_current_user
from src.api.schemas import (
    DriverLotsResponse,
    DriverLotDetail,
    OccupancyHistoryItem,
    PipelineStatusResponse,
)
from src.api.utils import get_latest_occupancies, lot_to_summary
from src.micro.state_engine import slot_state_engine, SlotState
from src.pipeline.orchestrator import pipeline

router = APIRouter(prefix="/api/v1/driver", tags=["driver"])


def _batch_slot_type_counts(
    db, lot_ids: list[str]
) -> dict[str, dict[str, int]]:
    rows = (
        db.query(
            MicroSlot.id,
            MicroSlot.lot_id,
            MicroSlot.slot_type,
            MicroSlot.slot_index,
        )
        .filter(
            MicroSlot.lot_id.in_(lot_ids),
            MicroSlot.active == 1,
        )
        .all()
    )
    result = {}
    for lot_id in lot_ids:
        result[lot_id] = {"handicap": 0, "ev": 0, "regular": 0}
    counts = {}
    for r in rows:
        key = (r.lot_id, r.slot_type)
        counts[key] = counts.get(key, 0) + 1
        if r.slot_type not in result[r.lot_id]:
            result[r.lot_id][r.slot_type] = 0
        result[r.lot_id][r.slot_type] += 1
    for r in rows:
        total = counts.get((r.lot_id, r.slot_type), 0)
        if total == 0:
            continue
        state = slot_state_engine.get_state(r.id)
        if state != SlotState.AVAILABLE:
            result[r.lot_id][r.slot_type] -= 1
    for lot_id in lot_ids:
        for st in ("handicap", "ev", "regular"):
            result[lot_id][st] = max(0, result[lot_id].get(st, 0))
    return result


@router.get("/lots", response_model=DriverLotsResponse)
async def search_lots(
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Max records to return"
    ),
    slot_type: str = Query(None, description="Filter by slot type"),
    max_price: Optional[float] = Query(
        None, ge=0, description="Max hourly price"
    ),
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    lots = db.query(ParkingLot).offset(offset).limit(limit).all()
    lot_ids = [lot.lot_id for lot in lots]
    latest_map = get_latest_occupancies(db, lot_ids) if lot_ids else {}
    batch_counts = _batch_slot_type_counts(db, lot_ids) if lot_ids else {}
    lots_data = []
    for lot in lots:
        latest = latest_map.get(lot.lot_id)
        summary = lot_to_summary(lot, latest)
        sc = batch_counts.get(
            lot.lot_id, {"handicap": 0, "ev": 0, "regular": 0}
        )
        summary["current_occupancy"] = latest.occupancy_rate if latest else 0.0
        summary["available_handicap"] = sc["handicap"]
        summary["available_ev"] = sc["ev"]
        summary["available_regular"] = sc["regular"]
        lots_data.append(summary)
    enriched = pipeline.driver_search_lots(lots_data)
    if slot_type:
        enriched = [
            lot for lot in enriched if lot.get(f"available_{slot_type}", 0) > 0
        ]
    if max_price is not None:
        enriched = [
            lot
            for lot in enriched
            if lot.get("dynamic_price", 999) <= max_price
        ]
    return DriverLotsResponse(lots=enriched)


@router.get("/lots/{lot_id}", response_model=DriverLotDetail)
async def lot_detail(
    lot_id: str = Path(..., pattern=r"^[a-zA-Z0-9_-]{1,50}$"),
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    lot = db.query(ParkingLot).filter(ParkingLot.lot_id == lot_id).first()
    if not lot:
        raise HTTPException(404, "Lot not found")
    records = (
        db.query(OccupancyRecord)
        .filter(
            OccupancyRecord.lot_id == lot_id,
        )
        .order_by(OccupancyRecord.timestamp.desc())
        .limit(24)
        .all()
    )
    latest = records[0] if records else None
    occ = latest.occupancy_rate if latest else 0.0
    cur_price = latest.price if latest else lot.base_price
    sc = _batch_slot_type_counts(db, [lot_id]).get(
        lot_id, {"handicap": 0, "ev": 0, "regular": 0}
    )
    enriched = pipeline.driver_search_lots(
        [
            {
                "lot_id": lot.lot_id,
                "name": lot.name,
                "address": lot.address,
                "total_slots": lot.total_slots,
                "base_price": lot.base_price,
                "price_cap": lot.price_cap,
                "current_occupancy": occ,
                "current_price": cur_price,
                "latitude": lot.latitude,
                "longitude": lot.longitude,
                "available_handicap": sc["handicap"],
                "available_ev": sc["ev"],
                "available_regular": sc["regular"],
            }
        ]
    )
    prediction = enriched[0] if enriched else {}
    return DriverLotDetail(
        lot_id=lot.lot_id,
        name=lot.name,
        address=lot.address,
        city=lot.city or "",
        total_slots=lot.total_slots,
        base_price=lot.base_price,
        latitude=lot.latitude,
        longitude=lot.longitude,
        predicted_occupancy=prediction.get(
            "predicted_occupancy", round(occ, 3)
        ),
        current_price=prediction.get("dynamic_price", cur_price),
        available_spots=prediction.get(
            "available_spots", max(0, int(lot.total_slots * (1 - occ)))
        ),
        available_handicap=sc["handicap"],
        available_ev=sc["ev"],
        available_regular=sc["regular"],
        recent_occupancy=[
            OccupancyHistoryItem(
                timestamp=r.timestamp.replace(
                    tzinfo=timezone.utc).isoformat() if r.timestamp else None,
                occupancy_rate=r.occupancy_rate,
                price=r.price,
                net_flux=r.net_flux,
            )
            for r in records
        ],
    )


@router.get("/pipeline/status", response_model=PipelineStatusResponse)
async def pipeline_status(user: dict = Depends(get_current_user)):
    return pipeline.status()
