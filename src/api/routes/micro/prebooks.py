import logging
import uuid
import time as time_module
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from src.api.database import get_db, ParkingLot, MicroSlot, PrebookRecord
from src.api.auth import get_current_user
from src.api.utils import driver_id
from src.api.schemas import (
    PrebookRequest,
    PrebookResponse,
    ConfirmPrebookRequest,
    ConfirmPrebookResponse,
)
from src.constants import RESERVATION_ACTIVE, RESERVATION_EXPIRED
from src.micro.state_engine import slot_state_engine, MAX_PREBOOK_HOURS, PREBOOK_GRACE_S
from src.micro.models import SlotState
from src.micro.pricing import slot_pricing
from .helpers import _rank_slots, _find_fallback_slot, _prebook_limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="", tags=["Micro Prebooks"])


@router.post("/prebook", response_model=PrebookResponse)
async def prebook_slot(
    body: PrebookRequest, user: dict = Depends(get_current_user), db=Depends(get_db)
):
    did = driver_id(user)
    logger.info("event=micro.prebook.starting lot=%s driver=%s", body.lot_id, did)
    if not _prebook_limiter.check(f"prebook:{did}"):
        raise HTTPException(429, "Too many prebook requests — rate limited")
    try:
        target_dt = datetime.fromisoformat(body.target_time)
    except (ValueError, TypeError):
        raise HTTPException(400, "Invalid target_time format (use ISO 8601)")
    if target_dt.tzinfo is not None:
        offset = target_dt.utcoffset()
        if offset is not None:
            target_dt = target_dt.replace(tzinfo=None) - offset
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    target_mono = time_module.monotonic() + (target_dt - now_utc).total_seconds()
    max_lookahead = MAX_PREBOOK_HOURS * 3600
    if target_mono > time_module.monotonic() + max_lookahead:
        raise HTTPException(
            400, f"Target time exceeds max prebook window of {MAX_PREBOOK_HOURS}h"
        )
    try:
        lot = db.query(ParkingLot).filter(ParkingLot.lot_id == body.lot_id).first()
        if not lot:
            raise HTTPException(404, "Lot not found")
        modifiers = slot_pricing.compute_modifiers([])
        ranked = _rank_slots(db, body.slots, lot, modifiers, did)
        if not ranked:
            raise HTTPException(400, "No valid slots found in request")
        assigned = None
        for entry in ranked:
            if entry["state"] == SlotState.AVAILABLE:
                st = entry["slot"]
                success = slot_state_engine.prebook(st.id, did, target_mono)
                if success:
                    assigned = entry
                    break
        if not assigned:
            raise HTTPException(409, "None of the requested slots are available")
        st = assigned["slot"]
        prebook_id = str(uuid.uuid4())[:16]
        expires_at = target_dt + timedelta(seconds=PREBOOK_GRACE_S)
        price = assigned["price"]
        prob = assigned["probability"]
        prebook_record = PrebookRecord(
            prebook_id=prebook_id,
            lot_id=body.lot_id,
            driver_id=did,
            slot_id=st.id,
            slot_index=st.slot_index,
            ranked_order=0,
            target_time=target_dt,
            expires_at=expires_at,
            probability_given=prob,
            price_at_booking=price,
            status=RESERVATION_ACTIVE,
        )
        db.add(prebook_record)
        db.commit()
        fallback = [r["slot_index"] for r in ranked[1:3]] if len(ranked) > 1 else None
        logger.info(
            "event=micro.prebook.completed lot=%s driver=%s", body.lot_id, did
        )
        return PrebookResponse(
            prebook_id=prebook_id,
            lot_id=body.lot_id,
            assigned_slot_index=st.slot_index,
            slot_label=f"{st.row_label}{st.position}",
            probability=prob,
            price_at_booking=price,
            expires_at=expires_at.isoformat(),
            status=RESERVATION_ACTIVE,
            fallback_order=fallback,
        )
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception(
            "event=micro.prebook.failed lot=%s driver=%s", body.lot_id, did
        )
        raise HTTPException(500, "Prebooking failed")


@router.post("/confirm", response_model=ConfirmPrebookResponse)
async def confirm_prebook(
    body: ConfirmPrebookRequest,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    did = driver_id(user)
    try:
        prebook = (
            db.query(PrebookRecord)
            .filter(
                PrebookRecord.prebook_id == body.prebook_id,
                PrebookRecord.driver_id == did,
            )
            .first()
        )
        if not prebook:
            raise HTTPException(404, "Prebooking not found")
        if prebook.status != RESERVATION_ACTIVE:
            raise HTTPException(400, f"Prebooking is already {prebook.status}")
        if datetime.now(timezone.utc).replace(tzinfo=None) > prebook.expires_at:
            prebook.status = RESERVATION_EXPIRED
            slot_state_engine.cleanup_expired(force=True)
            db.commit()
            raise HTTPException(410, "Prebooking has expired")
        if not slot_state_engine.confirm_prebook(prebook.slot_id, did):
            fb = _find_fallback_slot(db, prebook, did)
            if fb:
                fb.status = "confirmed"
                prebook.status = "unavailable"
                db.commit()
                slot = (
                    db.query(MicroSlot).filter(MicroSlot.id == fb.slot_id).first()
                )
                return ConfirmPrebookResponse(
                    prebook_id=fb.prebook_id,
                    slot_id=fb.slot_id,
                    slot_index=fb.slot_index,
                    slot_label=f"{slot.row_label}{slot.position}" if slot else "",
                    final_price=float(prebook.price_at_booking),
                    status="confirmed",
                )
            prebook.status = "unavailable"
            db.commit()
            raise HTTPException(
                409, "Requested slot unavailable and no fallback available"
            )
        prebook.status = "confirmed"
        db.commit()
        from src.api.services.session_service import create_session

        result = create_session(
            lot_id=prebook.lot_id,
            slot=prebook.slot_index,
            driver_id=did,
        )
        slot = db.query(MicroSlot).filter(MicroSlot.id == prebook.slot_id).first()
        return ConfirmPrebookResponse(
            session_id=result["session_id"],
            prebook_id=prebook.prebook_id,
            slot_id=prebook.slot_id,
            slot_index=prebook.slot_index,
            slot_label=f"{slot.row_label}{slot.position}" if slot else "",
            final_price=float(prebook.price_at_booking),
            status="confirmed",
        )
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(500, "Confirmation failed")
