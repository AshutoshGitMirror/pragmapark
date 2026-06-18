import logging
import uuid
import time as time_module
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from src.api.database import (
    get_db,
    ParkingLot,
    MicroSlot,
    PrebookRecord,
    User,
    Transaction,
)
from src.api.auth import get_current_user
from src.api.utils import driver_id
from src.api.schemas import (
    CancelPrebookResponse,
    ConfirmPrebookRequest,
    ConfirmPrebookResponse,
    PrebookListResponse,
    PrebookRequest,
    PrebookResponse,
)
from src.api.services.session_service import create_session as _mk_session
from src.constants import (
    RESERVATION_ACTIVE,
    RESERVATION_CONFIRMED,
    RESERVATION_CANCELLED,
    RESERVATION_NO_SHOW,
    RESERVATION_REFUNDED,
    BOOKING_FEE,
    DEPOSIT_RATE,
    DEFAULT_BASE_PRICE,
    TX_ACTION_BOOKING_FEE,
    TX_ACTION_DEPOSIT,
    TX_COMPLETED,
    ADMIN_FEE_RATE,
)
from src.micro.state_engine import (
    slot_state_engine,
    MAX_PREBOOK_HOURS,
    PREBOOK_GRACE_S,
)
from src.micro.models import SlotState
from src.micro.pricing import slot_pricing
from .helpers import _rank_slots, _find_fallback_slot, _prebook_limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="", tags=["Micro Prebooks"])


@router.post("/prebook", response_model=PrebookResponse)
async def prebook_slot(
    body: PrebookRequest,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    did = driver_id(user)
    logger.info(
        "event=micro.prebook.starting lot=%s driver=%s", body.lot_id, did
    )
    if not _prebook_limiter.check(f"prebook:{did}"):
        raise HTTPException(429, "Too many prebook requests — rate limited")
    try:
        target_dt = datetime.fromisoformat(body.target_time)
    except (ValueError, TypeError):
        raise HTTPException(400, "Invalid target_time format (use ISO 8601)")
    if target_dt.tzinfo is None:
        target_dt = target_dt.replace(tzinfo=timezone.utc)
    else:
        target_dt = target_dt.astimezone(timezone.utc)
    target_epoch = target_dt.timestamp()
    if target_epoch > time_module.time() + MAX_PREBOOK_HOURS * 3600:
        raise HTTPException(
            400,
            f"Target time exceeds max prebook window of {MAX_PREBOOK_HOURS}h",
        )
    try:
        lot = (
            db.query(ParkingLot)
            .filter(ParkingLot.lot_id == body.lot_id)
            .first()
        )
        if not lot:
            raise HTTPException(404, "Lot not found")

        all_lot_slots = (
            db.query(MicroSlot)
            .filter(
                MicroSlot.lot_id == body.lot_id,
                MicroSlot.active == 1,
            )
            .all()
        )
        modifiers = slot_pricing.compute_modifiers(all_lot_slots)
        ranked = _rank_slots(db, body.slots, lot, modifiers, did)
        if not ranked:
            raise HTTPException(400, "No valid slots found in request")

        # Calculate wallet deduction first (Issue 4: validate before mutating)
        base_price = (
            float(lot.base_price) if lot.base_price else DEFAULT_BASE_PRICE
        )
        deposit_amount = base_price * DEPOSIT_RATE
        total_deduction = BOOKING_FEE + deposit_amount

        driver = db.query(User).filter(User.email == did).first()
        if not driver:
            raise HTTPException(404, "Driver account not found")
        current_balance = float(driver.balance or 0.0)
        if current_balance < total_deduction:
            raise HTTPException(
                400,
                f"Insufficient balance. Need ${total_deduction:.2f}, have ${
                    current_balance:.2f}",
            )

        assigned = None
        for rank, entry in enumerate(ranked, start=1):
            if entry["state"] == SlotState.AVAILABLE:
                st = entry["slot"]
                success = slot_state_engine.prebook(st.id, did, target_epoch)
                if success:
                    assigned = entry
                    assigned["_rank"] = rank
                    break
        if not assigned:
            raise HTTPException(
                409, "None of the requested slots are available"
            )
        st = assigned["slot"]
        prebook_id = str(uuid.uuid4())
        target_dt_naive = target_dt.replace(tzinfo=None)
        expires_at = target_dt_naive + timedelta(seconds=PREBOOK_GRACE_S)
        price = assigned["price"]
        prob = assigned["probability"]

        driver.balance = current_balance - total_deduction

        fee_tx = Transaction(
            tx_hash=f"fee_{prebook_id}",
            lot_id=body.lot_id,
            driver_id=did,
            action=TX_ACTION_BOOKING_FEE,
            amount=BOOKING_FEE,
            status=TX_COMPLETED,
        )
        db.add(fee_tx)

        deposit_tx = Transaction(
            tx_hash=f"deposit_{prebook_id}",
            lot_id=body.lot_id,
            driver_id=did,
            action=TX_ACTION_DEPOSIT,
            amount=deposit_amount,
            status=TX_COMPLETED,
        )
        db.add(deposit_tx)

        prebook_record = PrebookRecord(
            prebook_id=prebook_id,
            lot_id=body.lot_id,
            driver_id=did,
            slot_id=st.id,
            slot_index=st.slot_index,
            ranked_order=assigned["_rank"],
            target_time=target_dt_naive,
            expires_at=expires_at,
            probability_given=prob,
            price_at_booking=price,
            status=RESERVATION_ACTIVE,
            booking_fee=BOOKING_FEE,
            deposit=deposit_amount,
        )
        db.add(prebook_record)
        db.commit()
        fallback = (
            [r["slot_index"] for r in ranked[1:3]] if len(ranked) > 1 else None
        )
        logger.info(
            "event=micro.prebook.completed lot=%s driver=%s deducted=%.2f",
            body.lot_id,
            did,
            total_deduction,
        )
        return PrebookResponse(
            prebook_id=prebook_id,
            lot_id=body.lot_id,
            assigned_slot_index=st.slot_index,
            slot_index=st.slot_index,
            slot_label=f"{st.row_label}{st.position}",
            probability=prob,
            price_at_booking=price,
            booking_fee=BOOKING_FEE,
            deposit=deposit_amount,
            expires_at=expires_at.isoformat() + "Z",
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
        if (
            datetime.now(timezone.utc).replace(tzinfo=None)
            > prebook.expires_at
        ):
            prebook.status = RESERVATION_NO_SHOW
            slot_state_engine.cleanup_expired(force=True)
            raise HTTPException(
                410, "Prebooking has expired — deposit forfeited"
            )

        def _confirm_and_create(prebook, did, db):
            result = _mk_session(
                lot_id=prebook.lot_id,
                slot=prebook.slot_index,
                driver_id=did,
            )
            slot_state_engine.confirm_prebook(prebook.slot_id, did)
            prebook.status = RESERVATION_CONFIRMED
            db.commit()
            return result

        if slot_state_engine.get_state(prebook.slot_id) in (
            SlotState.PREBOOKED,
            SlotState.RESERVED,
        ):
            result = _confirm_and_create(prebook, did, db)
            slot = (
                db.query(MicroSlot)
                .filter(MicroSlot.id == prebook.slot_id)
                .first()
            )
            return ConfirmPrebookResponse(
                session_id=result["session_id"],
                prebook_id=prebook.prebook_id,
                slot_id=prebook.slot_id,
                slot_index=prebook.slot_index,
                slot_label=f"{slot.row_label}{slot.position}" if slot else "",
                final_price=float(prebook.price_at_booking),
                status=RESERVATION_CONFIRMED,
            )

        target_dt = prebook.target_time
        if target_dt is not None:
            target_ts = target_dt.replace(tzinfo=timezone.utc).timestamp()
            if slot_state_engine.prebook(prebook.slot_id, did, target_ts):
                result = _confirm_and_create(prebook, did, db)
                slot = (
                    db.query(MicroSlot)
                    .filter(MicroSlot.id == prebook.slot_id)
                    .first()
                )
                return ConfirmPrebookResponse(
                    session_id=result["session_id"],
                    prebook_id=prebook.prebook_id,
                    slot_id=prebook.slot_id,
                    slot_index=prebook.slot_index,
                    slot_label=f"{slot.row_label}{slot.position}"
                    if slot
                    else "",
                    final_price=float(prebook.price_at_booking),
                    status=RESERVATION_CONFIRMED,
                )

        fb = _find_fallback_slot(db, prebook, did)
        if fb:
            fb_result = _mk_session(
                lot_id=fb.lot_id,
                slot=fb.slot_index,
                driver_id=did,
            )
            slot_state_engine.confirm_prebook(fb.slot_id, did)
            fb.status = RESERVATION_CONFIRMED
            prebook.status = "unavailable"
            db.commit()
            slot = (
                db.query(MicroSlot).filter(MicroSlot.id == fb.slot_id).first()
            )
            return ConfirmPrebookResponse(
                session_id=fb_result["session_id"],
                prebook_id=fb.prebook_id,
                slot_id=fb.slot_id,
                slot_index=fb.slot_index,
                slot_label=f"{slot.row_label}{slot.position}" if slot else "",
                final_price=float(fb.price_at_booking),
                status="confirmed",
            )

        deposit_amount = float(prebook.deposit or 0.0)
        if deposit_amount > 0 and not prebook.deposit_refunded:
            driver = db.query(User).filter(User.email == did).first()
            if driver:
                driver.balance = float(driver.balance or 0.0) + deposit_amount
                prebook.deposit_refunded = 1
                refund_tx = Transaction(
                    tx_hash=f"refund_{prebook.prebook_id}",
                    lot_id=prebook.lot_id,
                    driver_id=did,
                    action="refund",
                    amount=deposit_amount,
                    status=TX_COMPLETED,
                )
                db.add(refund_tx)
                logger.info(
                    "event=micro.confirm.prediction_fail_refund "
                    "driver=%s amount=%.2f",
                    did,
                    deposit_amount,
                )
        prebook.status = RESERVATION_REFUNDED
        db.commit()
        raise HTTPException(
            409, "Requested slot unavailable and no fallback available"
        )
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(500, "Confirmation failed")


@router.get("/prebooks/list", response_model=PrebookListResponse)
async def list_prebooks(
    user: dict = Depends(get_current_user), db=Depends(get_db)
):
    did = driver_id(user)
    records = (
        db.query(PrebookRecord)
        .filter(PrebookRecord.driver_id == did)
        .order_by(PrebookRecord.created_at.desc())
        .all()
    )
    slot_ids = list(set(r.slot_id for r in records if r.slot_id))
    lot_ids = list(set(r.lot_id for r in records))
    slots = (
        {
            s.id: s
            for s in db.query(MicroSlot)
            .filter(MicroSlot.id.in_(slot_ids))
            .all()
        }
        if slot_ids
        else {}
    )
    lots = (
        {
            lot.lot_id: lot
            for lot in db.query(ParkingLot)
            .filter(ParkingLot.lot_id.in_(lot_ids))
            .all()
        }
        if lot_ids
        else {}
    )

    def z(dt):
        return dt.isoformat() + "Z" if dt else None

    result = []
    for rec in records:
        slot = slots.get(rec.slot_id)
        lot = lots.get(rec.lot_id)
        result.append(
            {
                "prebook_id": rec.prebook_id,
                "lot_id": rec.lot_id,
                "lot_name": lot.name if lot else rec.lot_id,
                "driver_id": rec.driver_id,
                "slot_index": rec.slot_index,
                "slot_label": f"{slot.row_label}{slot.position}"
                if slot
                else "",
                "target_time": z(rec.target_time),
                "expires_at": z(rec.expires_at),
                "probability_given": float(rec.probability_given)
                if rec.probability_given is not None
                else None,
                "price_at_booking": float(rec.price_at_booking)
                if rec.price_at_booking is not None
                else None,
                "status": rec.status,
                "booking_fee": float(rec.booking_fee)
                if rec.booking_fee is not None
                else None,
                "deposit": float(rec.deposit)
                if rec.deposit is not None
                else None,
                "deposit_refunded": bool(rec.deposit_refunded),
                "created_at": z(rec.created_at),
            }
        )
    return {"prebooks": result}


@router.post("/cancel", response_model=CancelPrebookResponse)
async def cancel_prebook(
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

        if not slot_state_engine.release_prebook(prebook.slot_id, did):
            raise HTTPException(
                409, "Failed to release slot — engine state mismatch"
            )

        deposit_amount = float(prebook.deposit or 0.0)
        if deposit_amount > 0 and not prebook.deposit_refunded:
            refund_amount = deposit_amount * (1 - ADMIN_FEE_RATE)
            driver = db.query(User).filter(User.email == did).first()
            if driver:
                driver.balance = float(driver.balance or 0.0) + refund_amount
                prebook.deposit_refunded = 1
                refund_tx = Transaction(
                    tx_hash=f"cancel_{prebook.prebook_id}",
                    lot_id=prebook.lot_id,
                    driver_id=did,
                    action="refund",
                    amount=refund_amount,
                    status=TX_COMPLETED,
                )
                db.add(refund_tx)
                logger.info(
                    "event=micro.cancel.refund driver=%s deposit=%.2f "
                    "refund=%.2f admin_fee=%.2f",
                    did,
                    deposit_amount,
                    refund_amount,
                    deposit_amount * ADMIN_FEE_RATE,
                )
        prebook.status = RESERVATION_CANCELLED
        db.commit()
        return CancelPrebookResponse(
            status="cancelled",
            prebook_id=prebook.prebook_id,
            refund_amount=deposit_amount * (1 - ADMIN_FEE_RATE)
            if deposit_amount > 0 else 0.0,
            message="Prebooking cancelled. Deposit refunded (less admin fee)."
            if deposit_amount > 0 else "Prebooking cancelled.",
        )
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(500, "Cancellation failed")
