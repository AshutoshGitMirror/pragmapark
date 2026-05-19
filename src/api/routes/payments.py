from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import logging

from src.api.database import get_session as db_session, ParkingSession, Transaction
from src.api.auth import get_current_user
from src.pipeline.orchestrator import pipeline

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/payments", tags=["payments"])

class ConfirmPaymentRequest(BaseModel):
    session_id: str = Field(min_length=1)

@router.post("/confirm")
async def confirm_payment(req: ConfirmPaymentRequest, user: dict = Depends(get_current_user)):
    driver_id = user.get("sub") or user.get("email", "unknown")
    db = db_session()
    try:
        sess = db.query(ParkingSession).filter(
            ParkingSession.session_id == req.session_id,
        ).with_for_update().first()
        if not sess:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
        if sess.driver_id != driver_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Session belongs to another driver")
        if sess.status == "paid":
            return {"status": "already_paid", "session_id": req.session_id}
        if sess.status != "completed":
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                "Session must be ended before payment")

        amount = sess.amount_charged
        result = pipeline.process_payment(
            session_id=req.session_id,
            driver_id=driver_id,
            amount=amount,
            lot_id=sess.lot_id,
        )

        tx = Transaction(
            tx_hash=result["tx_hash"],
            lot_id=sess.lot_id,
            driver_id=driver_id,
            action="payment",
            amount=amount,
            duration_minutes=sess.duration_minutes,
            status="completed",
            timestamp=datetime.now(timezone.utc),
        )
        db.add(tx)

        sess.payment_tx = result["tx_hash"]
        sess.status = "paid"
        db.commit()
        logger.info(f"Payment confirmed: {result['tx_hash']} for session {req.session_id}")
        return {"status": "confirmed", "data": result}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Payment failed: {e}")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Payment processing failed")
    finally:
        db.close()

@router.get("/history")
async def my_payments(user: dict = Depends(get_current_user)):
    driver_id = user.get("sub") or user.get("email", "unknown")
    db = db_session()
    try:
        txs = db.query(Transaction).filter(
            Transaction.driver_id == driver_id,
            Transaction.action == "payment",
        ).order_by(Transaction.timestamp.desc()).limit(50).all()
        return {
            "total_payments": len(txs),
            "payments": [
                {
                    "tx_hash": t.tx_hash,
                    "lot_id": t.lot_id,
                    "amount": t.amount,
                    "timestamp": t.timestamp.isoformat() if t.timestamp else None,
                    "status": t.status,
                }
                for t in txs
            ],
        }
    finally:
        db.close()
