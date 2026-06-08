import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, cast

from src.api.database import get_db_cm, ParkingSession, ParkingLot, OccupancyRecord, PredictionMetric, PrebookRecord, User, Transaction
from src.api.ledger_outbox import enqueue_outbox, process_pending
from src.features.builder import build_features_from_records
from src.pipeline.orchestrator import pipeline
from src.constants import (SESSION_STALE_HOURS, MIN_RECORDS_FOR_FEATURES,
                           SESSION_RUNNING, SESSION_CANCELLED,
                           FREE_GRACE_MINUTES, MIN_CHARGE_AMOUNT, TX_COMPLETED,
                           RESERVATION_ACTIVE, RESERVATION_CONFIRMED)
from src.api.utils import get_recent_records

logger = logging.getLogger(__name__)


def create_session(lot_id: str, slot: int, driver_id: str,
                   payment_method: Optional[str] = None,
                   flat_rate: bool = False,
                   model_version: str = "rf+xgb_ensemble_v2",
                   force: bool = False) -> dict:
    with get_db_cm() as db:
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=SESSION_STALE_HOURS)
            db.query(ParkingSession).filter(
                ParkingSession.driver_id == driver_id,
                ParkingSession.status == SESSION_RUNNING,
                ParkingSession.start_time < cutoff,
            ).update({"status": SESSION_CANCELLED, "end_time": datetime.now(timezone.utc)})

            existing = db.query(ParkingSession).filter(
                ParkingSession.driver_id == driver_id, ParkingSession.status == SESSION_RUNNING,
            ).first()
            if existing:
                if force:
                    db.query(ParkingSession).filter(ParkingSession.id == existing.id).update(
                        {"status": SESSION_CANCELLED, "end_time": datetime.now(timezone.utc)}
                    )
                    # NOTE: no commit here — will commit at function end with the new session
                    # in a single atomic transaction. This prevents the partial-commit bug
                    # where the old session is cancelled but the new one fails to create.
                else:
                    raise RuntimeError("driver already has an active session")

            lot = db.query(ParkingLot).filter(ParkingLot.lot_id == lot_id).first()
            if not lot:
                raise RuntimeError("lot not found")

            records = get_recent_records(db, lot_id, limit=10)
            features = build_features_from_records(list(records), cast(int, lot.total_slots)) if len(records) >= MIN_RECORDS_FOR_FEATURES else None
            latest_occ = records[0] if records else None

            result = pipeline.start_session(
                lot_id=lot_id, driver_id=driver_id, slot=slot,
                total_slots=cast(int, lot.total_slots),
                base_price=float(cast(Decimal, lot.base_price)),
                current_price=float(cast(Decimal, latest_occ.price if latest_occ else lot.base_price)),
                price_cap=float(cast(Decimal, lot.price_cap)), features=features,
            )

            entry_price = float(result["price_at_entry"])
            if flat_rate:
                entry_price = float(cast(Decimal, lot.base_price))

            db.add(ParkingSession(
                session_id=result["session_id"], lot_id=lot_id, driver_id=driver_id,
                slot=slot, start_time=datetime.fromisoformat(result["start_time"]),
                entry_price=entry_price, status=SESSION_RUNNING,
                blockchain_ref=result["blockchain_ref"],
                payment_method=payment_method,
            ))
            db.add(PredictionMetric(
                lot_id=lot_id, session_id=result["session_id"],
                predicted_occupancy=result["predicted_occupancy"], model_version=model_version,
            ))
            enqueue_outbox(db, {"type": "session_start", "session_id": result["session_id"],
                                "lot_id": lot_id, "driver_id": driver_id, "action": "session_fee",
                                "price_at_entry": result["price_at_entry"], "ipfs_cid": result["blockchain_ref"],
                                "timestamp": datetime.now(timezone.utc).isoformat()})
            db.commit()
            process_pending(db, pipeline)
            logger.info("Session %s started for driver %s at %s (pred_occ=%.3f)",
                         result["session_id"], driver_id, lot_id, result.get("predicted_occupancy", 0))
            return {**result, "price_at_entry": entry_price}
        except Exception:
            db.rollback()
            raise


def settle_session(db, sess, amount_charged: float) -> dict:
    overcharge = 0.0
    deposit_refund = 0.0

    prebook = db.query(PrebookRecord).filter(
        PrebookRecord.driver_id == sess.driver_id,
        PrebookRecord.lot_id == sess.lot_id,
        PrebookRecord.slot_index == sess.slot,
        PrebookRecord.status.in_([RESERVATION_ACTIVE, RESERVATION_CONFIRMED]),
    ).order_by(PrebookRecord.created_at.desc()).first()

    if prebook and float(prebook.deposit or 0.0) > 0 and not prebook.deposit_refunded:
        deposit_amount = float(prebook.deposit)
        if amount_charged > deposit_amount:
            overcharge = amount_charged - deposit_amount
            driver = db.query(User).filter(User.email == sess.driver_id).first()
            if driver:
                driver.balance = float(driver.balance or 0.0) - overcharge
                db.add(Transaction(
                    tx_hash=f"overcharge_{sess.session_id}",
                    lot_id=sess.lot_id,
                    driver_id=sess.driver_id,
                    action="session_fee",
                    amount=overcharge,
                    status=TX_COMPLETED,
                ))
                logger.info(
                    "event=sessions.settle_overcharge session=%s driver=%s overcharge=%.2f",
                    sess.session_id, sess.driver_id, overcharge,
                )
            else:
                logger.error(
                    "event=sessions.settle.driver_not_found session=%s driver_id=%s "
                    "cannot process overcharge=%.2f",
                    sess.session_id, sess.driver_id, overcharge,
                )
        else:
            deposit_refund = deposit_amount - amount_charged
            if deposit_refund > 0:
                driver = db.query(User).filter(User.email == sess.driver_id).first()
                if driver:
                    driver.balance = float(driver.balance or 0.0) + deposit_refund
                    db.add(Transaction(
                        tx_hash=f"settle_{sess.session_id}",
                        lot_id=sess.lot_id,
                        driver_id=sess.driver_id,
                        action="refund",
                        amount=deposit_refund,
                        status=TX_COMPLETED,
                    ))
                    logger.info(
                        "event=sessions.settle_refund session=%s driver=%s deposit=%.2f charge=%.2f refund=%.2f",
                        sess.session_id, sess.driver_id, deposit_amount, amount_charged, deposit_refund,
                    )
                else:
                    logger.error(
                        "event=sessions.settle.driver_not_found session=%s driver_id=%s "
                        "cannot process refund=%.2f",
                        sess.session_id, sess.driver_id, deposit_refund,
                    )
        prebook.deposit_refunded = True

    enqueue_outbox(db, {"type": "session_fee", "session_id": sess.session_id, "lot_id": sess.lot_id,
                        "driver_id": sess.driver_id, "action": "session_fee", "amount": amount_charged,
                        "entry_price": sess.entry_price, "final_price": sess.final_price,
                        "timestamp": datetime.now(timezone.utc).isoformat()})

    return {"overcharge": overcharge, "deposit_refund": deposit_refund}
