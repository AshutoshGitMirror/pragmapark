import logging
import math
import random
from fastapi import APIRouter, Depends, HTTPException, Path

from src.api.database import get_db, ParkingLot, MicroSlot
from src.api.auth import get_current_user
from src.api.utils import require_admin
from src.api.schemas import SeedSlotsResponse
from src.micro.models import SlotType
from src.constants import (
    SLOT_TYPE_REGULAR_MAX,
    SLOT_TYPE_HANDICAP_MAX,
    SLOT_TYPE_EV_MAX,
    SLOT_TYPE_COVERED_MAX,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="", tags=["Micro Admin"])


@router.post("/lots/{lot_id}/slots/seed", response_model=SeedSlotsResponse)
async def seed_slots(
    lot_id: str = Path(..., pattern=r"^[a-zA-Z0-9_-]{1,50}$"),
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    require_admin(user)
    try:
        lot = db.query(ParkingLot).filter(ParkingLot.lot_id == lot_id).first()
        if not lot:
            raise HTTPException(404, "Lot not found")
        existing = (
            db.query(MicroSlot).filter(MicroSlot.lot_id == lot_id).count()
        )
        if existing > 0:
            return SeedSlotsResponse(
                status="already_seeded",
                count=existing,
                total_slots=lot.total_slots,
            )

        total = lot.total_slots
        rows = max(1, math.ceil(total / 20))
        per_row = math.ceil(total / rows)
        created = 0
        for r in range(rows):
            row_label = chr(65 + r)
            for p in range(per_row):
                if created >= total:
                    break
                roll = random.random()
                if roll < SLOT_TYPE_REGULAR_MAX:
                    slot_type = SlotType.HANDICAP.value
                elif roll < SLOT_TYPE_HANDICAP_MAX:
                    slot_type = SlotType.EV.value
                elif roll < SLOT_TYPE_EV_MAX:
                    slot_type = SlotType.COVERED.value
                elif roll < SLOT_TYPE_COVERED_MAX:
                    slot_type = SlotType.PREMIUM.value
                else:
                    slot_type = SlotType.REGULAR.value
                db.add(
                    MicroSlot(
                        lot_id=lot_id,
                        slot_index=created + 1,
                        row_label=row_label,
                        position=p + 1,
                        slot_type=slot_type,
                        active=1,
                        base_modifier_score=random.uniform(0, 0.5),
                    )
                )
                created += 1
        db.commit()
        return SeedSlotsResponse(
            status="seeded", count=created, total_slots=total
        )
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("event=slot.seed.failed lot=%s", lot_id)
        raise HTTPException(500, "Slot seeding failed")
