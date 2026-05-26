import logging
import uuid
import time as time_module
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from datetime import datetime, timedelta, timezone
from typing import cast, Optional

from src.api.database import get_session as db_session, ParkingLot, MicroSlot, MicroZone, SlotReservation, PrebookRecord
from src.api.auth import get_current_user
from src.api.utils import require_admin, RateLimiter
from src.api.schemas import (
    SlotResponse, SlotProbabilityResponse, ReserveSlotRequest, ReserveSlotResponse,
    ReleaseSlotRequest, ReleaseSlotResponse, SlotsListResponse, MicroZoneResponse,
    SeedSlotsResponse, PrebookSlotItem, PrebookRequest, PrebookResponse,
    ConfirmPrebookRequest, ConfirmPrebookResponse,
)
from src.micro.state_engine import slot_state_engine, RESERVATION_TTL_S, MAX_PREBOOK_HOURS
from src.micro.pricing import slot_pricing
from src.micro.predictor import slot_predictor
from src.micro.models import SlotState

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/micro", tags=["Micro Slot"])

_reserve_limiter = RateLimiter(max_calls=10, window=60.0)
_release_limiter = RateLimiter(max_calls=10, window=60.0)
_slot_list_limiter = RateLimiter(max_calls=30, window=60.0)
_prebook_limiter = RateLimiter(max_calls=5, window=60.0)


def _slots_to_response(slots: list, lot, modifiers: list[float]) -> list[SlotResponse]:
    base_price = float(lot.base_price)
    out = []
    for s in slots:
        prob = slot_predictor.predict(s.id)
        base_mod = slot_pricing.slot_price(s, base_price, modifiers)
        adj = slot_pricing.slot_price(s, base_price, modifiers, probability=prob)
        out.append(SlotResponse(
            id=s.id, lot_id=s.lot_id, slot_index=s.slot_index,
            row_label=s.row_label, position=s.position,
            slot_type=s.slot_type, state=slot_state_engine.get_state(s.id).value,
            current_price=base_mod, probability=prob,
            probability_adjusted_price=adj,
            base_modifier_score=s.base_modifier_score,
        ))
    return out


def _rank_slots(slots: list[PrebookSlotItem], lot, modifiers: list[float], driver_id: str) -> list[dict]:
    base_price = float(lot.base_price)
    scored = []
    for item in slots:
        db_slot = _find_slot(lot.lot_id, item.slot_index)
        if not db_slot:
            continue
        prob = slot_predictor.predict(db_slot.id, target_time=None)
        state = slot_state_engine.get_state(db_slot.id)
        price = slot_pricing.slot_price(db_slot, base_price, modifiers, probability=prob)
        score = prob * 10 - price * 0.05
        scored.append(dict(
            slot_index=item.slot_index, slot=db_slot, probability=prob,
            price=price, score=score, state=state,
            priority=item.priority if item.priority is not None else 999,
        ))
    scored.sort(key=lambda x: (x["priority"], -x["score"]))
    return scored


def _find_slot(lot_id: str, slot_index: int):
    db = db_session()
    try:
        return db.query(MicroSlot).filter(
            MicroSlot.lot_id == lot_id, MicroSlot.slot_index == slot_index, MicroSlot.active == 1,
        ).first()
    finally:
        db.close()


@router.get("/lots/{lot_id}/slots", response_model=SlotsListResponse)
async def list_slots(lot_id: str = Path(..., pattern=r"^[a-zA-Z0-9_-]{1,50}$"),
                     offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000),
                     user: dict = Depends(get_current_user)):
    if not _slot_list_limiter.check(f"list:{user.get('sub','')}"):
        raise HTTPException(429, "Too many slot list requests — rate limited")
    db = db_session()
    try:
        lot = db.query(ParkingLot).filter(ParkingLot.lot_id == lot_id).first()
        if not lot:
            raise HTTPException(404, "Lot not found")
        slots = db.query(MicroSlot).filter(
            MicroSlot.lot_id == lot_id, MicroSlot.active == 1,
        ).order_by(MicroSlot.slot_index).offset(offset).limit(limit).all()
        if not slots:
            return SlotsListResponse(lot_id=lot_id, total_slots=0, available=0, reserved=0, occupied=0, prebooked=0, slots=[])
        states = slot_state_engine.occupancies(lot_id, slots)
        return SlotsListResponse(
            lot_id=lot_id, total_slots=states["total_slots"],
            available=states["available_slots"], reserved=states["reserved_slots"],
            occupied=states["occupied_slots"], prebooked=states.get("prebooked_slots", 0),
            slots=_slots_to_response(slots, lot, slot_pricing.compute_modifiers(slots)),
        )
    finally:
        db.close()


@router.get("/lots/{lot_id}/slots/{slot_index}/probability", response_model=SlotProbabilityResponse)
async def slot_probability(lot_id: str = Path(..., pattern=r"^[a-zA-Z0-9_-]{1,50}$"),
                           slot_index: int = Path(..., ge=1),
                           target_time: str = Query(""),
                           user: dict = Depends(get_current_user)):
    db = db_session()
    try:
        slot = db.query(MicroSlot).filter(
            MicroSlot.lot_id == lot_id, MicroSlot.slot_index == slot_index, MicroSlot.active == 1,
        ).first()
        if not slot:
            raise HTTPException(404, "Slot not found")
        lot = db.query(ParkingLot).filter(ParkingLot.lot_id == lot_id).first()
        prob = slot_predictor.predict(slot.id, target_time or None)
        state = slot_state_engine.get_state(slot.id)
        base_price = float(lot.base_price) if lot else 10.0
        modifiers = slot_pricing.compute_modifiers([slot])
        adj_price = slot_pricing.slot_price(slot, base_price, modifiers, probability=prob)
        return SlotProbabilityResponse(
            slot_id=slot.id, slot_label=f"{slot.row_label}{slot.position}",
            probability=prob, current_state=state.value,
            current_price=adj_price,
        )
    finally:
        db.close()


@router.get("/lots/{lot_id}/zones", response_model=list[MicroZoneResponse])
async def list_zones(lot_id: str = Path(..., pattern=r"^[a-zA-Z0-9_-]{1,50}$"),
                     offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000),
                     user: dict = Depends(get_current_user)):
    db = db_session()
    try:
        zones = db.query(MicroZone).filter(MicroZone.lot_id == lot_id).offset(offset).limit(limit).all()
        zone_ids = [z.id for z in zones]
        slots_by_zone: dict[int, list] = {zid: [] for zid in zone_ids}
        if zone_ids:
            for s in db.query(MicroSlot).filter(MicroSlot.micro_zone_id.in_(zone_ids)).all():
                slots_by_zone[s.micro_zone_id].append(s)
        return [MicroZoneResponse(
            id=z.id, name=z.name, slot_count=len(slots_by_zone[z.id]),
            available=slot_state_engine.occupancies(lot_id, slots_by_zone[z.id])["available_slots"],
            occupancy_rate=slot_state_engine.occupancies(lot_id, slots_by_zone[z.id])["occupancy_rate"],
        ) for z in zones]
    finally:
        db.close()


@router.post("/reserve", response_model=ReserveSlotResponse)
async def reserve_slot(body: ReserveSlotRequest, user: dict = Depends(get_current_user)):
    driver_id = user.get("sub") or user.get("email", "unknown")
    db = db_session()
    slot_id = None
    try:
        slot = db.query(MicroSlot).filter(
            MicroSlot.lot_id == body.lot_id, MicroSlot.slot_index == body.slot_index, MicroSlot.active == 1,
        ).first()
        if not slot:
            raise HTTPException(404, "Slot not found")
        slot_id = slot.id
        if not slot_state_engine.reserve(slot_id, driver_id):
            raise HTTPException(409, "Slot is not available")
        try:
            prob = slot_predictor.predict(slot_id, body.target_time or None)
            res = SlotReservation(
                slot_id=slot_id, driver_id=driver_id,
                target_time=datetime.fromisoformat(body.target_time) if body.target_time else datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=RESERVATION_TTL_S),
                probability_given=prob, status="active",
            )
            db.add(res)
            db.commit()
        except Exception:
            db.rollback()
            slot_state_engine.release(slot_id, driver_id)
            raise
        return ReserveSlotResponse(
            reservation_id=cast(int, res.id), slot_label=f"{slot.row_label}{slot.position}",
            slot_id=slot_id, probability=prob,
            expires_at=res.expires_at.isoformat(), status="active",
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, "Reservation failed")
    finally:
        db.close()


@router.post("/prebook", response_model=PrebookResponse)
async def prebook_slot(body: PrebookRequest, user: dict = Depends(get_current_user)):
    driver_id = user.get("sub") or user.get("email", "unknown")
    if not _prebook_limiter.check(f"prebook:{driver_id}"):
        raise HTTPException(429, "Too many prebook requests — rate limited")
    try:
        target_dt = datetime.fromisoformat(body.target_time)
    except (ValueError, TypeError):
        raise HTTPException(400, "Invalid target_time format (use ISO 8601)")
    target_mono = time_module.monotonic() + (target_dt - datetime.now(timezone.utc)).total_seconds()
    max_lookahead = MAX_PREBOOK_HOURS * 3600
    if target_mono > time_module.monotonic() + max_lookahead:
        raise HTTPException(400, f"Target time exceeds max prebook window of {MAX_PREBOOK_HOURS}h")
    db = db_session()
    try:
        lot = db.query(ParkingLot).filter(ParkingLot.lot_id == body.lot_id).first()
        if not lot:
            raise HTTPException(404, "Lot not found")
        modifiers = slot_pricing.compute_modifiers([])
        ranked = _rank_slots(body.slots, lot, modifiers, driver_id)
        if not ranked:
            raise HTTPException(400, "No valid slots found in request")
        assigned = None
        for entry in ranked:
            if entry["state"] == SlotState.AVAILABLE:
                st = entry["slot"]
                success = slot_state_engine.prebook(st.id, driver_id, target_mono)
                if success:
                    assigned = entry
                    break
        if not assigned:
            raise HTTPException(409, "None of the requested slots are available")
        st = assigned["slot"]
        prebook_id = str(uuid.uuid4())[:16]
        expires_at = target_dt + timedelta(seconds=1800)
        price = assigned["price"]
        prob = assigned["probability"]
        prebook_record = PrebookRecord(
            prebook_id=prebook_id, lot_id=body.lot_id, driver_id=driver_id,
            slot_id=st.id, slot_index=st.slot_index,
            ranked_order=0, target_time=target_dt,
            expires_at=expires_at, probability_given=prob,
            price_at_booking=price, status="active",
        )
        db.add(prebook_record)
        db.commit()
        fallback = [r["slot_index"] for r in ranked[1:3]] if len(ranked) > 1 else None
        return PrebookResponse(
            prebook_id=prebook_id, lot_id=body.lot_id,
            assigned_slot_index=st.slot_index, slot_label=f"{st.row_label}{st.position}",
            probability=prob, price_at_booking=price,
            expires_at=expires_at.isoformat(), status="active",
            fallback_order=fallback,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, "Prebooking failed")
    finally:
        db.close()


@router.post("/confirm", response_model=ConfirmPrebookResponse)
async def confirm_prebook(body: ConfirmPrebookRequest, user: dict = Depends(get_current_user)):
    driver_id = user.get("sub") or user.get("email", "unknown")
    db = db_session()
    try:
        prebook = db.query(PrebookRecord).filter(
            PrebookRecord.prebook_id == body.prebook_id, PrebookRecord.driver_id == driver_id,
        ).first()
        if not prebook:
            raise HTTPException(404, "Prebooking not found")
        if prebook.status != "active":
            raise HTTPException(400, f"Prebooking is already {prebook.status}")
        if datetime.now(timezone.utc).replace(tzinfo=None) > prebook.expires_at:
            prebook.status = "expired"
            slot_state_engine.cleanup_expired(force=True)
            db.commit()
            raise HTTPException(410, "Prebooking has expired")
        if not slot_state_engine.confirm_prebook(prebook.slot_id, driver_id):
            fallback_order = db.query(PrebookRecord).filter(
                PrebookRecord.driver_id == driver_id, PrebookRecord.lot_id == prebook.lot_id,
                PrebookRecord.status == "active", PrebookRecord.id != prebook.id,
            ).order_by(PrebookRecord.ranked_order).all()
            for fb in fallback_order:
                if slot_state_engine.confirm_prebook(fb.slot_id, driver_id):
                    fb.status = "confirmed"
                    prebook.status = "unavailable"
                    db.commit()
                    slot = db.query(MicroSlot).filter(MicroSlot.id == fb.slot_id).first()
                    return ConfirmPrebookResponse(
                        prebook_id=fb.prebook_id, slot_id=fb.slot_id,
                        slot_index=fb.slot_index, slot_label=f"{slot.row_label}{slot.position}" if slot else "",
                        final_price=float(prebook.price_at_booking), status="confirmed",
                    )
            prebook.status = "unavailable"
            db.commit()
            raise HTTPException(409, "Requested slot unavailable and no fallback available")
        prebook.status = "confirmed"
        db.commit()
        from src.api.routes.sessions import start_session
        from src.api.schemas import StartSessionRequest
        session_req = StartSessionRequest(lot_id=prebook.lot_id, slot=prebook.slot_index)
        session_resp = await start_session(session_req, user)
        slot = db.query(MicroSlot).filter(MicroSlot.id == prebook.slot_id).first()
        return ConfirmPrebookResponse(
            session_id=session_resp.session_id, prebook_id=prebook.prebook_id,
            slot_id=prebook.slot_id, slot_index=prebook.slot_index,
            slot_label=f"{slot.row_label}{slot.position}" if slot else "",
            final_price=float(prebook.price_at_booking), status="confirmed",
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, "Confirmation failed")
    finally:
        db.close()


@router.post("/release", response_model=ReleaseSlotResponse)
async def release_slot(body: ReleaseSlotRequest, user: dict = Depends(get_current_user)):
    if not _release_limiter.check(f"release:{user.get('sub','')}"):
        raise HTTPException(429, "Too many release requests — rate limited")
    driver_id = user.get("sub") or user.get("email", "unknown")
    db = db_session()
    try:
        res = db.query(SlotReservation).filter(
            SlotReservation.id == body.reservation_id, SlotReservation.driver_id == driver_id,
        ).first()
        if not res:
            raise HTTPException(404, "Reservation not found")
        if body.slot_id != res.slot_id:
            raise HTTPException(400, "Slot ID does not match reservation")
        if not slot_state_engine.release(body.slot_id, driver_id):
            raise HTTPException(400, "Could not release slot")
        res.status = "released"
        db.commit()
        return ReleaseSlotResponse(status="released", slot_id=body.slot_id)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, "Release failed")
    finally:
        db.close()


@router.post("/lots/{lot_id}/slots/seed", response_model=SeedSlotsResponse)
async def seed_slots(lot_id: str = Path(..., pattern=r"^[a-zA-Z0-9_-]{1,50}$"),
                     user: dict = Depends(get_current_user)):
    require_admin(user)
    db = db_session()
    try:
        lot = db.query(ParkingLot).filter(ParkingLot.lot_id == lot_id).first()
        if not lot:
            raise HTTPException(404, "Lot not found")
        existing = db.query(MicroSlot).filter(MicroSlot.lot_id == lot_id).count()
        if existing > 0:
            return SeedSlotsResponse(status="already_seeded", count=existing, total_slots=lot.total_slots)
        import math, random
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
                slot_type = "regular"
                if roll < 0.05: slot_type = "handicap"
                elif roll < 0.10: slot_type = "ev"
                elif roll < 0.25: slot_type = "covered"
                elif roll < 0.30: slot_type = "premium"
                db.add(MicroSlot(
                    lot_id=lot_id, slot_index=created + 1,
                    row_label=row_label, position=p + 1,
                    slot_type=slot_type, active=1,
                    base_modifier_score=random.uniform(0, 0.5),
                ))
                created += 1
        db.commit()
        return SeedSlotsResponse(status="seeded", count=created, total_slots=total)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, "Slot seeding failed")
    finally:
        db.close()
