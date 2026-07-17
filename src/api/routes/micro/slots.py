import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Path

from src.api.database import get_db, ParkingLot, MicroSlot

from src.api.schemas import SlotsListResponse, SlotProbabilityResponse
from src.micro.state_engine import slot_state_engine
from src.micro.pricing import slot_pricing
from src.micro.predictor import slot_predictor
from .helpers import _slots_to_response, _slot_list_limiter
from src.micro.resident_map import slot_resident_mapping

logger = logging.getLogger(__name__)
router = APIRouter(prefix="", tags=["Micro Slots"])


@router.get("/lots/{lot_id}/slots", response_model=SlotsListResponse)
async def list_slots(
    lot_id: str = Path(..., pattern=r"^[a-zA-Z0-9_-]{1,50}$"),
    offset: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=1000),
    db=Depends(get_db),
):
    if not _slot_list_limiter.check(f"slots:{lot_id}"):
        raise HTTPException(429, "Too many slot list requests — rate limited")
    lot = db.query(ParkingLot).filter(ParkingLot.lot_id == lot_id).first()
    if not lot:
        raise HTTPException(404, "Lot not found")
    all_slots = (
        db.query(MicroSlot)
        .filter(
            MicroSlot.lot_id == lot_id,
            MicroSlot.active == 1,
        )
        .order_by(MicroSlot.slot_index)
        .all()
    )
    if not all_slots:
        return SlotsListResponse(
            lot_id=lot_id,
            total_slots=0,
            available=0,
            reserved=0,
            occupied=0,
            prebooked=0,
            slots=[],
        )
    states = slot_state_engine.occupancies(lot_id, all_slots)
    resident_ids = slot_resident_mapping.get_resident_only_slot_ids(lot_id)
    states["available_slots"] = max(0, states["available_slots"] - len(resident_ids))
    page = all_slots[offset: offset + limit]
    return SlotsListResponse(
        lot_id=lot_id,
        total_slots=len(all_slots),
        available=states["available_slots"],
        reserved=states["reserved_slots"],
        occupied=states["occupied_slots"],
        prebooked=states.get("prebooked_slots", 0),
        slots=_slots_to_response(
            page, lot, slot_pricing.compute_modifiers(page),
            resident_only_ids=resident_ids,
        ),
    )


@router.get(
    "/lots/{lot_id}/slots/{slot_index}/probability",
    response_model=SlotProbabilityResponse,
)
async def slot_probability(
    lot_id: str = Path(..., pattern=r"^[a-zA-Z0-9_-]{1,50}$"),
    slot_index: int = Path(..., ge=1),
    target_time: str = Query(""),
    db=Depends(get_db),
):
    slot = (
        db.query(MicroSlot)
        .filter(
            MicroSlot.lot_id == lot_id,
            MicroSlot.slot_index == slot_index,
            MicroSlot.active == 1,
        )
        .first()
    )
    if not slot:
        raise HTTPException(404, "Slot not found")
    lot = db.query(ParkingLot).filter(ParkingLot.lot_id == lot_id).first()
    prob = slot_predictor.predict(slot.id, target_time or None)
    state = slot_state_engine.get_state(slot.id)
    base_price = float(lot.base_price) if lot else 10.0
    modifiers = slot_pricing.compute_modifiers([slot])
    adj_price = slot_pricing.slot_price(
        slot, base_price, modifiers, probability=prob
    )
    return SlotProbabilityResponse(
        slot_id=slot.id,
        slot_label=f"{slot.row_label}{slot.position}",
        probability=prob,
        current_state=state.value,
        current_price=adj_price,
    )
