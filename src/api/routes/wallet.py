from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
import logging

from src.api.database import User, get_db
from src.api.auth import get_current_user
from src.constants import DRIVER_DEFAULT_BALANCE

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
    u = db.query(User).filter(User.id == user["id"]).first()
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return WalletResponse(balance=float(u.balance or 0.0))


@router.post("/topup", response_model=TopupResponse)
async def topup_wallet(req: TopupRequest, user: dict = Depends(get_current_user), db=Depends(get_db)):
    u = db.query(User).filter(User.id == user["id"]).first()
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    u.balance = float(u.balance or 0.0) + req.amount
    db.commit()
    logger.info("event=wallet.topup user=%s amount=%.2f new_balance=%.2f", user["id"], req.amount, u.balance)
    return TopupResponse(balance=u.balance, amount_added=req.amount)
