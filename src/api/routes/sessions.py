from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from datetime import datetime, timedelta, timezone
import logging
import os

from src.api.database import get_session as db_session, get_recent_records, ParkingSession, ParkingLot, OccupancyRecord, PredictionMetric
from src.api.auth import get_current_user
from src.api.schemas import StartSessionRequest, EndSessionRequest, SessionStartResponse, SessionEndResponse, SessionHistoryResponse, ActiveSessionsResponse, ActiveSessionItem, SessionHistoryItem, SessionReceiptResponse, SessionDetailResponse, PricingBreakdownResponse
from src.pipeline.orchestrator import pipeline
from src.features.builder import build_features_from_records

_MODEL_VERSION = os.getenv("MODEL_VERSION", "rf+xgb_ensemble_v2")
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


def _driver_id(user: dict) -> str:
    return user.get("email") or user.get("sub", "unknown")


@router.post("/start", response_model=SessionStartResponse)
async def start_session(req: StartSessionRequest, user: dict = Depends(get_current_user)):
    driver_id = _driver_id(user)
    db = db_session()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        db.query(ParkingSession).filter(
            ParkingSession.driver_id == driver_id,
            ParkingSession.status == "active",
            ParkingSession.start_time < cutoff,
        ).update({"status": "expired", "end_time": datetime.now(timezone.utc)})

        existing = db.query(ParkingSession).filter(
            ParkingSession.driver_id == driver_id, ParkingSession.status == "active",
        ).first()
        if existing:
            if req.force:
                existing.status = "expired"
                existing.end_time = datetime.now(timezone.utc)
                db.commit()
            else:
                raise HTTPException(status.HTTP_409_CONFLICT, "You already have an active session")

        lot = db.query(ParkingLot).filter(ParkingLot.lot_id == req.lot_id).first()
        if not lot:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Lot not found")

        records = get_recent_records(db, req.lot_id, limit=10)
        features = build_features_from_records(list(records), lot.total_slots) if len(records) >= 5 else None
        latest_occ = records[-1] if records else None

        result = pipeline.start_session(
            lot_id=req.lot_id, driver_id=driver_id, slot=req.slot,
            total_slots=lot.total_slots, base_price=lot.base_price,
            current_price=latest_occ.price if latest_occ else lot.base_price,
            price_cap=lot.price_cap, features=features,
        )

        entry_price = result["price_at_entry"]
        if req.flat_rate:
            entry_price = lot.base_price

        db.add(ParkingSession(
            session_id=result["session_id"], lot_id=req.lot_id, driver_id=driver_id,
            slot=req.slot, start_time=datetime.fromisoformat(result["start_time"]),
            entry_price=entry_price, status="active",
            blockchain_ref=result["blockchain_ref"],
            payment_method=req.payment_method,
        ))
        db.add(PredictionMetric(
            lot_id=req.lot_id, session_id=result["session_id"],
            predicted_occupancy=result["predicted_occupancy"], model_version=_MODEL_VERSION,
        ))
        from src.api.ledger_outbox import enqueue_outbox, process_pending
        enqueue_outbox(db, {"type": "session_start", "session_id": result["session_id"],
                            "lot_id": req.lot_id, "driver_id": driver_id, "action": "park",
                            "price_at_entry": result["price_at_entry"], "ipfs_cid": result["blockchain_ref"]})
        db.commit()
        process_pending(db, pipeline)
        logger.info("Session %s started for driver %s at %s (pred_occ=%.3f)",
                     result["session_id"], driver_id, req.lot_id, result.get("predicted_occupancy", 0))
        return SessionStartResponse(**{**result, "price_at_entry": entry_price})
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to start session")
    finally:
        db.close()


@router.post("/end", response_model=SessionEndResponse)
async def end_session(req: EndSessionRequest, user: dict = Depends(get_current_user)):
    driver_id = _driver_id(user)
    db = db_session()
    try:
        sess = db.query(ParkingSession).filter(
            ParkingSession.session_id == req.session_id, ParkingSession.status == "active",
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
            total_slots=lot.total_slots if lot else 500,
            price_cap=lot.price_cap if lot else 200.0, slot=sess.slot,
        )

        sess.status = "completed"
        sess.end_time = datetime.fromisoformat(result["end_time"])
        sess.duration_minutes = int(result["duration_hours"] * 60)
        sess.final_price = result["final_price"]

        dur_mins = sess.duration_minutes or 0
        if dur_mins <= 15:
            result["amount_charged"] = 0.0
        amount_charged = max(result["amount_charged"], 1.0) if result["amount_charged"] > 0 else 0.0

        sess.amount_charged = amount_charged
        sess.blockchain_ref = result["blockchain_ref"]

        metric = db.query(PredictionMetric).filter(
            PredictionMetric.session_id == req.session_id,
        ).first()
        if metric and latest:
            metric.actual_occupancy = current_occ
            metric.mae = abs(metric.predicted_occupancy - current_occ)

        from src.api.ledger_outbox import enqueue_outbox, process_pending
        enqueue_outbox(db, {"type": "payment", "session_id": req.session_id, "lot_id": sess.lot_id,
                            "driver_id": sess.driver_id, "action": "payment", "amount": amount_charged,
                            "entry_price": sess.entry_price, "final_price": result["final_price"],
                            "ipfs_cid": result["blockchain_ref"]})
        db.commit()
        process_pending(db, pipeline)
        logger.info("Session %s ended, charged $%s", req.session_id, amount_charged)
        return SessionEndResponse(
            session_id=result["session_id"], lot_id=result["lot_id"],
            driver_id=result["driver_id"], duration_hours=result["duration_hours"],
            entry_price=result["entry_price"], final_price=result["final_price"],
            amount_charged=amount_charged, blockchain_ref=result["blockchain_ref"],
            end_time=result["end_time"], layers_activated=result["layers_activated"],
            duration_minutes=sess.duration_minutes, total_cost=amount_charged,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to end session")
    finally:
        db.close()


@router.get("/active/{lot_id}", response_model=ActiveSessionsResponse)
async def active_sessions(lot_id: str = Path(..., pattern=r"^[a-zA-Z0-9_-]{1,50}$"),
                          offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000),
                          user: dict = Depends(get_current_user)):
    db = db_session()
    try:
        q = db.query(ParkingSession).filter(
            ParkingSession.lot_id == lot_id, ParkingSession.status == "active",
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
    finally:
        db.close()


@router.get("/history", response_model=SessionHistoryResponse)
async def my_history(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=500),
                     user: dict = Depends(get_current_user)):
    driver_id = _driver_id(user)
    db = db_session()
    try:
        sessions = db.query(ParkingSession).filter(
            ParkingSession.driver_id == driver_id,
        ).order_by(ParkingSession.start_time.desc()).offset(offset).limit(limit).all()
        lot_ids = list(set(s.lot_id for s in sessions))
        lots_map = {}
        if lot_ids:
            lots = db.query(ParkingLot.lot_id, ParkingLot.name).filter(
                ParkingLot.lot_id.in_(lot_ids)
            ).all()
            lots_map = {l.lot_id: l.name for l in lots}
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
    finally:
        db.close()


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session_detail(session_id: str = Path(..., min_length=1, max_length=100),
                              user: dict = Depends(get_current_user)):
    db = db_session()
    try:
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
    finally:
        db.close()


@router.get("/{session_id}/pricing", response_model=PricingBreakdownResponse)
async def pricing_breakdown(session_id: str = Path(..., min_length=1, max_length=100),
                            user: dict = Depends(get_current_user)):
    db = db_session()
    try:
        sess = db.query(ParkingSession).filter(
            ParkingSession.session_id == session_id,
        ).first()
        if not sess:
            raise HTTPException(404, "Session not found")
        driver_id = _driver_id(user)
        if sess.driver_id != driver_id and user.get("role") != "admin":
            raise HTTPException(403, "Not your session")
        lot = db.query(ParkingLot).filter(ParkingLot.lot_id == sess.lot_id).first()
        bp = lot.base_price if lot else 10.0
        cap = lot.price_cap if lot else 200.0
        dh = (sess.duration_minutes or 0) / 60.0
        ep = sess.entry_price or 0.0
        mult = round(ep / bp, 4) if bp > 0 else 1.0
        breakdown = (
            f"Base price: ${bp:.2f} | Multiplier: {mult}x | Entry: ${ep:.2f} | "
            f"Duration: {dh:.2f}h | Final: ${sess.final_price:.2f} | "
            f"Charge: ${sess.amount_charged:.2f} | Cap: ${cap:.2f}"
        )
        return PricingBreakdownResponse(
            session_id=sess.session_id, lot_id=sess.lot_id,
            entry_price=ep, base_price=bp, price_multiplier=mult, price_cap=cap,
            final_price=sess.final_price, duration_hours=dh,
            amount_charged=sess.amount_charged, breakdown=breakdown,
        )
    finally:
        db.close()


@router.get("/{session_id}/receipt", response_model=SessionReceiptResponse)
async def session_receipt(session_id: str = Path(..., min_length=1, max_length=100),
                           user: dict = Depends(get_current_user)):
    db = db_session()
    try:
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
    finally:
        db.close()
