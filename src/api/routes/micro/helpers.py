import logging
from decimal import Decimal
from typing import Any, cast

from src.api.database import ParkingLot, MicroSlot, PrebookRecord
from src.constants import (
    PREBOOK_SCORE_PROB_WEIGHT,
    PREBOOK_SCORE_PRICE_PENALTY,
    PREBOOK_DEFAULT_PRIORITY,
    RESERVATION_ACTIVE,
)
from src.api.utils import DBRateLimiter
from src.api.schemas import SlotResponse, PrebookSlotItem
from src.micro.state_engine import slot_state_engine
from src.micro.pricing import slot_pricing
from src.micro.predictor import slot_predictor

logger = logging.getLogger(__name__)

_reserve_limiter = DBRateLimiter(max_calls=10, window=60.0, prefix="reserve")
_release_limiter = DBRateLimiter(max_calls=10, window=60.0, prefix="release")
_slot_list_limiter = DBRateLimiter(max_calls=30, window=60.0, prefix="slots")
_prebook_limiter = DBRateLimiter(max_calls=5, window=60.0, prefix="prebook")


def _slots_to_response(
    slots: list, lot: ParkingLot, modifiers: list[float],
    resident_only_ids: set[int] = set(),
) -> list[SlotResponse]:
    base_price = float(cast(Decimal, lot.base_price))
    out = []
    for s in slots:
        is_resident = s.id in resident_only_ids
        prob = slot_predictor.predict(cast(int, s.id))
        base_mod = slot_pricing.slot_price(s, base_price, modifiers)
        adj = slot_pricing.slot_price(
            s, base_price, modifiers, probability=prob
        )
        out.append(
            SlotResponse(
                id=s.id,
                lot_id=s.lot_id,
                slot_index=s.slot_index,
                row_label=s.row_label,
                position=s.position,
                slot_type=s.slot_type,
                state=slot_state_engine.get_state(s.id).value,
                current_price=base_mod,
                probability=prob,
                probability_adjusted_price=adj,
                base_modifier_score=s.base_modifier_score,
                is_resident_only=is_resident,
            )
        )
    return out


def _find_slot(db, lot_id: str, slot_index: int) -> MicroSlot | None:
    return (
        db.query(MicroSlot)
        .filter(
            MicroSlot.lot_id == lot_id,
            MicroSlot.slot_index == slot_index,
            MicroSlot.active == 1,
        )
        .first()
    )


def _rank_slots(
    db,
    slots: list[PrebookSlotItem],
    lot: ParkingLot,
    modifiers: list[float],
    driver_id: str,
) -> list[dict[str, Any]]:
    base_price = float(cast(Decimal, lot.base_price))
    scored = []
    for item in slots:
        db_slot = _find_slot(db, cast(str, lot.lot_id), item.slot_index)
        if not db_slot:
            continue
        prob = slot_predictor.predict(cast(int, db_slot.id), target_time=None)
        state = slot_state_engine.get_state(cast(int, db_slot.id))
        price = slot_pricing.slot_price(
            db_slot, base_price, modifiers, probability=prob
        )
        score = (
            prob * PREBOOK_SCORE_PROB_WEIGHT
            - price * PREBOOK_SCORE_PRICE_PENALTY
        )
        scored.append(
            dict(
                slot_index=item.slot_index,
                slot=db_slot,
                probability=prob,
                price=price,
                score=score,
                state=state,
                priority=(
                    item.priority
                    if item.priority is not None
                    else PREBOOK_DEFAULT_PRIORITY
                ),
            )
        )
    scored.sort(key=lambda x: (x["priority"], -x["score"]))
    return scored


def _find_fallback_slot(db, prebook, did):
    fallback_order = (
        db.query(PrebookRecord)
        .filter(
            PrebookRecord.driver_id == did,
            PrebookRecord.lot_id == prebook.lot_id,
            PrebookRecord.status == RESERVATION_ACTIVE,
            PrebookRecord.id != prebook.id,
        )
        .order_by(PrebookRecord.ranked_order)
        .all()
    )
    for fb in fallback_order:
        if slot_state_engine.confirm_prebook(fb.slot_id, did):
            return fb
    return None
