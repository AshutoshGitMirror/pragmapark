from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from datetime import datetime, timezone
import logging
import os

from src.api.database import get_db, ParkingSession, ParkingLot, OccupancyRecord, PredictionMetric, PrebookRecord, User, Transaction
from src.api.auth import get_current_user
from src.api.schemas import StartSessionRequest, EndSessionRequest, SessionStartResponse, SessionEndResponse, SessionHistoryResponse, ActiveSessionsResponse, ActiveSessionItem, SessionHistoryItem, SessionReceiptResponse, SessionDetailResponse, PricingBreakdownResponse
from src.pipeline.orchestrator import pipeline
from src.constants import DEFAULT_TOTAL_SLOTS, DEFAULT_PRICE_CAP, FREE_GRACE_MINUTES, MIN_CHARGE_AMOUNT, DEFAULT_BASE_PRICE, SESSION_RUNNING, SESSION_PENDING_SETTLEMENT, TX_COMPLETED
from src.api.utils import driver_id as _driver_id
from src.api.services.session_service import create_session

_MODEL_VERSION = os.getenv("MODEL_VERSION", "rf+xgb_ensemble_v2")
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.post("/start", response_model=SessionStartResponse)
async def start_session(req: StartSessionRequest, user: dict = Depends(get_current_user)):
    did = _driver_id(user)
    try:
        result = create_session(
            lot_id=req.lot_id, slot=req.slot, driver_id=did,
            payment_method=req.payment_method,
            flat_rate=req.flat_rate,
            model_version=_MODEL_VERSION,
            force=req.force,
        )
        return SessionStartResponse(**result)
    except RuntimeError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to start session")


@router.post("/end", response_model=SessionEndResponse)
async def end_session(req: EndSessionRequest, user: dict = Depends(get_current_user), db = Depends(get_db)):
    driver_id = _driver_id(user)
    try:
        sess = db.query(ParkingSession).filter(
            ParkingSession.session_id == req.session_id, ParkingSession.status == SESSION_RUNNING,
        ).first()
        if not sess:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Active session not found")
        if sess.driver_id != driver_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Session belongs to another driver")

        lot = db.query(ParkingLot).filter(ParkingLot.lot_id == sess.lot_id).first()
        latest = db.query(OccupancyRecord).filter(
            OccupancyRecord.lot_id == sess.lot_id,
        ).order_by(OccupancyRecord.timestamp.desc()).first()
        current_occ = latest.occupancy_rate if latest else 0.5

        result = pipeline.end_session(
            session_id=sess.session_id, lot_id=sess.lot_id, driver_id=sess.driver_id,
            start_time=sess.start_time.isoformat() if sess.start_time else datetime.now(timezone.utc).isoformat(),
            current_occupancy=current_occ, entry_price=sess.entry_price,
            total_slots=lot.total_slots if lot else DEFAULT_TOTAL_SLOTS,
            price_cap=lot.price_cap if lot else DEFAULT_PRICE_CAP, slot=sess.slot,
        )

        sess.status = SESSION_PENDING_SETTLEMENT
        sess.end_time = datetime.fromisoformat(result["end_time"])
        sess.duration_minutes = int(result["duration_hours"] * 60)
        sess.final_price = float(result["final_price"])

        dur_mins = sess.duration_minutes or 0
        if dur_mins <= FREE_GRACE_MINUTES:
            result["amount_charged"] = 0.0
        amount_charged = max(result["amount_charged"], MIN_CHARGE_AMOUNT) if result["amount_charged"] > 0 else 0.0

        sess.amount_charged = amount_charged
        sess.blockchain_ref = result["blockchain_ref"]

        # Wallet settlement (Option D)
        prebook = db.query(PrebookRecord).filter(
            PrebookRecord.driver_id == driver_id,
            PrebookRecord.slot_index == sess.slot,
            PrebookRecord.status == "confirmed",
        ).order_by(PrebookRecord.created_at.desc()).first()
        
        deposit_refund = 0.0
        if prebook and float(prebook.deposit or 0.0) > 0 and not prebook.deposit_refunded:
            deposit_amount = float(prebook.deposit)
            # Refund delta: deposit - actual charge
            deposit_refund = max(0.0, deposit_amount - amount_charged)
            if deposit_refund > 0:
                driver = db.query(User).filter(User.email == driver_id).first()
                if driver:
                    driver.balance = float(driver.balance or 0.0) + deposit_refund
                    prebook.deposit_refunded = 1
                    # Record refund transaction
                    refund_tx = Transaction(
                        tx_hash=f"settle_{sess.session_id}",
                        lot_id=sess.lot_id,
                        driver_id=driver_id,
                        action="refund",
                        amount=deposit_refund,
                        status=TX_COMPLETED,
                    )
                    db.add(refund_tx)
                    logger.info(
                        "event=sessions.settle_refund session=%s driver=%s deposit=%.2f charge=%.2f refund=%.2f",
                        sess.session_id, driver_id, deposit_amount, amount_charged, deposit_refund,
                    )

        metric = db.query(PredictionMetric).filter(
            PredictionMetric.session_id == req.session_id,
        ).first()
        if metric and latest:
            metric.actual_occupancy = current_occ
            metric.mae = abs(metric.predicted_occupancy - current_occ)

        from src.api.ledger_outbox import enqueue_outbox, process_pending
        from src.api.database import MicroSlot
        enqueue_outbox(db, {"type": "session_fee", "session_id": req.session_id, "lot_id": sess.lot_id,
                            "driver_id": sess.driver_id, "action": "session_fee", "amount": amount_charged,
                            "entry_price": sess.entry_price, "final_price": result["final_price"],
                            "ipfs_cid": result["blockchain_ref"]})
        db.commit()
        process_pending(db, pipeline)
        slot_rec = db.query(MicroSlot).filter(
            MicroSlot.lot_id == sess.lot_id, MicroSlot.slot_index == sess.slot,
        ).first()
        slot_label = f"{slot_rec.row_label}{slot_rec.position}" if slot_rec else ""
        logger.info(
            "event=sessions.end session=%s driver=%s lot=%s slot=%d charge=%.2f refund=%.2f",
            req.session_id, driver_id, sess.lot_id, sess.slot, amount_charged, deposit_refund,
        )
        return SessionEndResponse(
            session_id=result["session_id"], lot_id=result["lot_id"],
            driver_id=result["driver_id"], duration_hours=result["duration_hours"],
            entry_price=result["entry_price"], final_price=result["final_price"],
            amount_charged=amount_charged, blockchain_ref=result["blockchain_ref"],
            end_time=result["end_time"], layers_activated=result["layers_activated"],
            duration_minutes=sess.duration_minutes, total_cost=amount_charged,
            slot=sess.slot, slot_label=slot_label, deposit_refund=deposit_refund,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("event=sessions.end.failed session=%s driver=%s error=%s", req.session_id, driver_id, e)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to end session")


@router.get("/active/{lot_id}", response_model=ActiveSessionsResponse)
async def active_sessions(lot_id: str = Path(..., pattern=r"^[a-zA-Z0-9_-]{1,50}$"),
                          offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000),
                          user: dict = Depends(get_current_user),
                          db = Depends(get_db)):
    q = db.query(ParkingSession).filter(
        ParkingSession.lot_id == lot_id, ParkingSession.status == SESSION_RUNNING,
    )
    if user.get("role") != "admin":
        q = q.filter(ParkingSession.driver_id == user.get("sub"))
    sessions = q.offset(offset).limit(limit).all()
    return ActiveSessionsResponse(
        lot_id=lot_id, active_count=len(sessions),
        sessions=[ActiveSessionItem(
            session_id=s.session_id, slot=s.slot,
            start_time=s.start_time.isoformat() if s.start_time else None,
            entry_price=s.entry_price,
        ) for s in sessions],
    )


@router.get("/history", response_model=SessionHistoryResponse)
async def my_history(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=500),
                     user: dict = Depends(get_current_user),
                     db = Depends(get_db)):
    driver_id = _driver_id(user)
    sessions = db.query(ParkingSession).filter(
        ParkingSession.driver_id == driver_id,
    ).order_by(ParkingSession.start_time.desc()).offset(offset).limit(limit).all()
    lot_ids = list(set(s.lot_id for s in sessions))
    lots_map = {}
    if lot_ids:
        lots = db.query(ParkingLot.lot_id, ParkingLot.name).filter(
            ParkingLot.lot_id.in_(lot_ids)
        ).all()
        lots_map = {lot.lot_id: lot.name for lot in lots}
    return SessionHistoryResponse(
        total_sessions=len(sessions),
        sessions=[SessionHistoryItem(
            session_id=s.session_id, lot_id=s.lot_id,
            lot_name=lots_map.get(s.lot_id) or s.lot_id,
            start_time=s.start_time.isoformat() if s.start_time else None,
            end_time=s.end_time.isoformat() if s.end_time else None,
            duration_minutes=s.duration_minutes, amount_charged=s.amount_charged,
            status=s.status,
        ) for s in sessions],
    )


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session_detail(session_id: str = Path(..., min_length=1, max_length=100),
                              user: dict = Depends(get_current_user),
                              db = Depends(get_db)):
    sess = db.query(ParkingSession).filter(
        ParkingSession.session_id == session_id,
    ).first()
    if not sess:
        raise HTTPException(404, "Session not found")
    driver_id = _driver_id(user)
    if sess.driver_id != driver_id and user.get("role") != "admin":
        raise HTTPException(403, "Session belongs to another driver")
    return SessionDetailResponse(
        session_id=sess.session_id, lot_id=sess.lot_id,
        slot=sess.slot, driver_id=sess.driver_id, status=sess.status,
        start_time=sess.start_time.isoformat() if sess.start_time else None,
        end_time=sess.end_time.isoformat() if sess.end_time else None,
        duration_minutes=sess.duration_minutes,
        entry_price=sess.entry_price, final_price=sess.final_price,
        amount_charged=sess.amount_charged, blockchain_ref=sess.blockchain_ref,
        payment_method=getattr(sess, "payment_method", "card"),
    )


@router.get("/{session_id}/pricing", response_model=PricingBreakdownResponse)
async def pricing_breakdown(session_id: str = Path(..., min_length=1, max_length=100),
                            user: dict = Depends(get_current_user),
                            db = Depends(get_db)):
    sess = db.query(ParkingSession).filter(
        ParkingSession.session_id == session_id,
    ).first()
    if not sess:
        raise HTTPException(404, "Session not found")
    driver_id = _driver_id(user)
    if sess.driver_id != driver_id and user.get("role") != "admin":
        raise HTTPException(403, "Not your session")
    lot = db.query(ParkingLot).filter(ParkingLot.lot_id == sess.lot_id).first()
    base_price = lot.base_price if lot else DEFAULT_BASE_PRICE
    price_cap = lot.price_cap if lot else DEFAULT_PRICE_CAP
    duration_hours = (sess.duration_minutes or 0) / 60.0
    entry_price = sess.entry_price or 0.0
    price_multiplier = round(entry_price / base_price, 4) if base_price > 0 else 1.0
    breakdown = (
        f"Base price: ${base_price:.2f} | Multiplier: {price_multiplier}x | Entry: ${entry_price:.2f} | "
        f"Duration: {duration_hours:.2f}h | Final: ${sess.final_price:.2f} | "
        f"Charge: ${sess.amount_charged:.2f} | Cap: ${price_cap:.2f}"
    )
    return PricingBreakdownResponse(
        session_id=sess.session_id, lot_id=sess.lot_id,
        entry_price=entry_price, base_price=base_price, price_multiplier=price_multiplier, price_cap=price_cap,
        final_price=sess.final_price, duration_hours=duration_hours,
        amount_charged=sess.amount_charged, breakdown=breakdown,
    )


@router.get("/{session_id}/receipt", response_model=SessionReceiptResponse)
async def session_receipt(session_id: str = Path(..., min_length=1, max_length=100),
                           user: dict = Depends(get_current_user),
                           db = Depends(get_db)):
    sess = db.query(ParkingSession).filter(
        ParkingSession.session_id == session_id,
        ParkingSession.driver_id == _driver_id(user),
    ).first()
    if not sess:
        raise HTTPException(404, "Session not found")
    return SessionReceiptResponse(
        session_id=sess.session_id, lot_id=sess.lot_id,
        driver_id=sess.driver_id,
        start_time=sess.start_time.isoformat() if sess.start_time else None,
        end_time=sess.end_time.isoformat() if sess.end_time else None,
        duration_minutes=sess.duration_minutes or 0,
        duration_hours=(sess.duration_minutes or 0) / 60.0,
        entry_price=sess.entry_price,
        final_price=sess.final_price,
        amount_charged=sess.amount_charged,
        blockchain_ref=sess.blockchain_ref,
        payment_method=getattr(sess, "payment_method", "card"),
    )
