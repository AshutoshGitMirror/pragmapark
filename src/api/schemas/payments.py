from typing import List, Optional

from pydantic import BaseModel, Field


class PaymentConfirmRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    idempotency_key: str = Field(default="", max_length=64)


class PaymentConfirmResponse(BaseModel):
    session_id: str
    tx_hash: str = ""
    transaction_id: str = ""
    blockchain_ref: str = ""
    amount: float = 0.0
    amount_charged: float = 0.0
    ledger_blocks: int = 0
    already_paid: bool = False
    status: str = ""


class PaymentHistoryItem(BaseModel):
    tx_hash: str
    lot_id: str
    amount: float
    timestamp: Optional[str]
    status: str


class PaymentHistoryResponse(BaseModel):
    total_payments: int
    payments: List[PaymentHistoryItem]
