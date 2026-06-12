import logging
from datetime import datetime, timedelta, timezone
from typing import cast

from fastapi import APIRouter, Depends, HTTPException

from src.api.database import get_db, MicroSlot, SlotReservation
from src.api.auth import get_current_user
from src.api.utils import driver_id
from src.api.schemas import (
    ReserveSlotRequest,
    ReserveSlotResponse,
    ReleaseSlotRequest,
    ReleaseSlotResponse,
)
from src.constants import RESERVATION_ACTIVE
from src.micro.state_engine import slot_state_engine, RESERVATION_TTL_S
from src.micro.predictor import slot_predictor
from .helpers import _release_limiter, _reserve_limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="", tags=["Micro Reservations"])


@router.post("/reserve", response_model=ReserveSlotResponse)
async def reserve_slot(
    body: ReserveSlotRequest,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    if not _reserve_limiter.check(f"reserve:{user.get('sub', '')}"):
        raise HTTPException(
            429, "Too many reservation requests — rate limited"
        )
    did = driver_id(user)
    logger.info(
        "event=micro.reserve.starting slot=%s driver=%s", body.slot_index, did
    )
    slot_id = None
    try:
        slot = (
            db.query(MicroSlot)
            .filter(
                MicroSlot.lot_id == body.lot_id,
                MicroSlot.slot_index == body.slot_index,
                MicroSlot.active == 1,
            )
            .first()
        )
        if not slot:
            raise HTTPException(404, "Slot not found")
        slot_id = slot.id
        if not slot_state_engine.reserve(slot_id, did):
            raise HTTPException(409, "Slot is not available")
        try:
            prob = slot_predictor.predict(slot_id, body.target_time or None)
            res = SlotReservation(
                slot_id=slot_id,
                driver_id=did,
                target_time=(
                    datetime.fromisoformat(body.target_time)
                    if body.target_time
                    else datetime.now(timezone.utc)
                ),
                expires_at=datetime.now(timezone.utc)
                + timedelta(seconds=RESERVATION_TTL_S),
                probability_given=prob,
                status=RESERVATION_ACTIVE,
            )
            db.add(res)
            db.commit()
        except Exception:
            db.rollback()
            slot_state_engine.release(slot_id, did)
            raise
        logger.info(
            "event=micro.reserve.completed slot=%s driver=%s",
            body.slot_index,
            did,
        )
        return ReserveSlotResponse(
            reservation_id=cast(int, res.id),
            slot_label=f"{slot.row_label}{slot.position}",
            slot_id=slot_id,
            probability=prob,
            expires_at=res.expires_at.isoformat() + "Z",
            status=RESERVATION_ACTIVE,
        )
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception(
            "event=micro.reserve.failed slot=%s driver=%s",
            body.slot_index,
            did,
        )
        raise HTTPException(500, "Reservation failed")


@router.post("/release", response_model=ReleaseSlotResponse)
async def release_slot(
    body: ReleaseSlotRequest,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    if not _release_limiter.check(f"release:{user.get('sub', '')}"):
        raise HTTPException(429, "Too many release requests — rate limited")
    did = driver_id(user)
    logger.info(
        "event=micro.release.starting slot=%s driver=%s", body.slot_id, did
    )
    try:
        res = (
            db.query(SlotReservation)
            .filter(
                SlotReservation.id == body.reservation_id,
                SlotReservation.driver_id == did,
            )
            .first()
        )
        if not res:
            raise HTTPException(404, "Reservation not found")
        if body.slot_id != res.slot_id:
            raise HTTPException(400, "Slot ID does not match reservation")
        if not slot_state_engine.release(body.slot_id, did):
            raise HTTPException(400, "Could not release slot")
        res.status = "released"
        db.commit()
        logger.info(
            "event=micro.release.completed slot=%s driver=%s",
            body.slot_id,
            did,
        )
        return ReleaseSlotResponse(status="released", slot_id=body.slot_id)
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception(
            "event=micro.release.failed slot=%s driver=%s", body.slot_id, did
        )
        raise HTTPException(500, "Release failed")
