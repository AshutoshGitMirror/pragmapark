from typing import List, Optional
from datetime import datetime

from pydantic import BaseModel


class RevenueCumulativeResponse(BaseModel):
    total_revenue: float = 0.0
    total_sessions: int = 0
    total_lots: int = 0
    total_drivers: int = 0
    avg_revenue_per_session: float = 0.0
    avg_revenue_per_lot: float = 0.0


class RevenueOverviewItem(BaseModel):
    lot_id: str
    name: str
    total_revenue: float
    total_transactions: int
    avg_daily_revenue: float


class RevenueOverviewResponse(BaseModel):
    total_revenue: float
    total_transactions: int
    daily: List[RevenueOverviewItem]


class TransactionHistoryItem(BaseModel):
    tx_hash: str
    lot_id: str
    driver_id: str
    action: str
    amount: float
    duration_minutes: int
    status: str
    timestamp: Optional[str] = None


class WalletTransactionResponse(BaseModel):
    tx_hash: str
    action: str
    amount: float
    status: str
    lot_id: Optional[str] = None
    timestamp: datetime
    session_id: Optional[str] = None
