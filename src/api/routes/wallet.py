from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
import logging
from datetime import datetime, timezone

from src.api.database import User, Transaction, get_db
from src.api.auth import get_current_user
from src.constants import DRIVER_DEFAULT_BALANCE, TX_COMPLETED

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/wallet", tags=["wallet"])


class WalletResponse(BaseModel):
    balance: float
    currency: str = "USD"


class TopupRequest(BaseModel):
    amount: float = Field(gt=0, le=100000)


class TopupResponse(BaseModel):
    balance: float
    amount_added: float
    message: str = "Top-up successful"


@router.get("", response_model=WalletResponse)
async def get_balance(user: dict = Depends(get_current_user), db=Depends(get_db)):
    uid = user.get("user_id") or user.get("id")
    u = db.query(User).filter(User.id == uid).first()
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return WalletResponse(balance=float(u.balance or 0.0))


@router.post("/topup", response_model=TopupResponse)
async def topup_wallet(req: TopupRequest, user: dict = Depends(get_current_user), db=Depends(get_db)):
    uid = user.get("user_id") or user.get("id")
    u = db.query(User).filter(User.id == uid).first()
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    u.balance = float(u.balance or 0.0) + req.amount
    driver_email = user.get("sub") or u.email
    db.add(Transaction(
        tx_hash=f"topup_{uid}_{datetime.now(timezone.utc).isoformat()}",
        lot_id=None,
        driver_id=driver_email,
        action="deposit",
        amount=req.amount,
        status=TX_COMPLETED,
        timestamp=datetime.now(timezone.utc),
    ))
    db.commit()
    logger.info("event=wallet.topup user=%s amount=%.2f new_balance=%.2f", uid, req.amount, u.balance)
    return TopupResponse(balance=u.balance, amount_added=req.amount)
