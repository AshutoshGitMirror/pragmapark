from fastapi import APIRouter, Depends, Query, Path

from src.api.database import get_db, MicroZone, MicroSlot
from src.api.auth import get_current_user
from src.api.schemas import MicroZoneResponse
from src.micro.state_engine import slot_state_engine

router = APIRouter(prefix="", tags=["Micro Zones"])


@router.get("/lots/{lot_id}/zones", response_model=list[MicroZoneResponse])
async def list_zones(
    lot_id: str = Path(..., pattern=r"^[a-zA-Z0-9_-]{1,50}$"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    zones = (
        db.query(MicroZone)
        .filter(MicroZone.lot_id == lot_id)
        .offset(offset)
        .limit(limit)
        .all()
    )
    zone_ids = [z.id for z in zones]
    slots_by_zone: dict[int, list] = {zid: [] for zid in zone_ids}
    if zone_ids:
        for s in (
            db.query(MicroSlot).filter(MicroSlot.micro_zone_id.in_(zone_ids)).all()
        ):
            slots_by_zone[s.micro_zone_id].append(s)
    occ_data = {
        zid: slot_state_engine.occupancies(lot_id, slots_by_zone[zid])
        for zid in zone_ids
    }
    return [
        MicroZoneResponse(
            id=z.id,
            name=z.name,
            slot_count=len(slots_by_zone[z.id]),
            available=occ_data[z.id]["available_slots"],
            occupancy_rate=occ_data[z.id]["occupancy_rate"],
        )
        for z in zones
    ]
