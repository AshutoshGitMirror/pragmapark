from fastapi import APIRouter, Depends, HTTPException, status, Query
from datetime import datetime, timezone
import logging

from src.api.database import get_db, ParkingSession, Transaction, RevenueRecord
from src.api.auth import get_current_user
from src.api.ledger_outbox import enqueue_outbox, process_pending
from src.api.schemas import (
    PaymentConfirmRequest,
    PaymentConfirmResponse,
    PaymentHistoryResponse,
    PaymentHistoryItem,
)
from src.pipeline.orchestrator import pipeline
from src.api.utils import driver_id
from src.constants import SESSION_SETTLED, SESSION_PENDING_SETTLEMENT

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


@router.post("/confirm", response_model=PaymentConfirmResponse)
def confirm_payment(
    req: PaymentConfirmRequest,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    did = driver_id(user)
    try:
        sess = (
            db.query(ParkingSession)
            .filter(
                ParkingSession.session_id == req.session_id,
            )
            .first()
        )
        if not sess:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
        if sess.driver_id != did:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Session belongs to another driver"
            )
        if sess.status == SESSION_SETTLED:
            return PaymentConfirmResponse(
                session_id=req.session_id,
                tx_hash=sess.payment_tx or "",
                transaction_id=sess.payment_tx or "",
                blockchain_ref=sess.payment_blockchain_ref
                or sess.payment_tx
                or "",
                already_paid=True,
                status=SESSION_SETTLED,
            )
        if sess.status != SESSION_PENDING_SETTLEMENT:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Session must be ended before payment",
            )

        if req.idempotency_key:
            existing_tx = (
                db.query(Transaction)
                .filter(
                    Transaction.idempotency_key == req.idempotency_key,
                )
                .first()
            )
            if existing_tx:
                return PaymentConfirmResponse(
                    session_id=req.session_id,
                    tx_hash=existing_tx.tx_hash,
                    transaction_id=existing_tx.tx_hash,
                    blockchain_ref=existing_tx.blockchain_ref or "",
                    already_paid=True,
                    status=SESSION_SETTLED,
                )

        amount = sess.amount_charged
        result = pipeline.process_payment(
            session_id=req.session_id,
            driver_id=did,
            amount=amount,
            lot_id=sess.lot_id,
        )

        tx = Transaction(
            tx_hash=result["tx_hash"],
            session_id=req.session_id,
            lot_id=sess.lot_id,
            driver_id=did,
            action="session_fee",
            amount=amount,
            duration_minutes=sess.duration_minutes,
            status="completed",
            idempotency_key=req.idempotency_key or None,
            timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.add(tx)

        sess.payment_tx = result["tx_hash"]
        sess.payment_blockchain_ref = result["blockchain_ref"]
        sess.status = SESSION_SETTLED

        today = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        rev = (
            db.query(RevenueRecord)
            .filter(
                RevenueRecord.lot_id == sess.lot_id,
                RevenueRecord.date == today,
            )
            .first()
        )
        if rev:
            rev.total_transactions += 1
            rev.total_revenue += amount or 0
            rev.avg_price = rev.total_revenue / rev.total_transactions
        else:
            rev = RevenueRecord(
                lot_id=sess.lot_id,
                date=today,
                total_transactions=1,
                total_revenue=amount or 0,
                avg_price=amount or 0,
            )
            db.add(rev)
        enqueue_outbox(
            db,
            {
                "type": "payment_confirmation",
                "session_id": req.session_id,
                "driver_id": did,
                "lot_id": sess.lot_id,
                "action": "session_fee",
                "amount": amount,
                "tx_hash": result["tx_hash"],
                "ipfs_cid": result["blockchain_ref"],
            },
        )
        db.commit()
        process_pending(db, pipeline)
        pipeline.flush_ledger()
        logger.info(
            "Payment confirmed: %s for session %s",
            result.get("tx_hash", ""),
            req.session_id,
        )
        charged_amount = result.get("amount", 0.0)
        return PaymentConfirmResponse(
            session_id=result["session_id"],
            tx_hash=result["tx_hash"],
            transaction_id=result["tx_hash"],
            amount=charged_amount,
            amount_charged=charged_amount,
            blockchain_ref=result["blockchain_ref"],
            ledger_blocks=result["ledger_blocks"],
            status=SESSION_SETTLED,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Payment failed: %s", e)
        logger.exception("Payment failed")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "Payment processing failed"
        )


@router.get("/history", response_model=PaymentHistoryResponse)
def my_payments(
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=500, description="Max records to return"),
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    did = driver_id(user)
    base = db.query(Transaction).filter(
        Transaction.driver_id == did,
        Transaction.action == "session_fee",
    )
    total_payments = base.count()
    txs = (
        base.order_by(Transaction.timestamp.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return PaymentHistoryResponse(
        total_payments=total_payments,
        payments=[
            PaymentHistoryItem(
                tx_hash=t.tx_hash,
                lot_id=t.lot_id,
                amount=t.amount,
                timestamp=t.timestamp.replace(
                    tzinfo=timezone.utc).isoformat() if t.timestamp else None,
                status=t.status,
            )
            for t in txs
        ],
    )
