from typing import List, Optional

from pydantic import BaseModel, Field
from src.constants import PAYMENT_METHODS


class StartSessionRequest(BaseModel):
    lot_id: str = Field(
        min_length=1, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$"
    )
    slot: int = Field(default=0, ge=0, le=100000)
    force: bool = Field(
        default=False,
        description="Force-start: ends any existing active session first",
    )
    flat_rate: bool = Field(
        default=False,
        description="Use lot base_price instead of dynamic pricing",
    )
    payment_method: str = Field(
        default="card",
        pattern=r"^(card|cash)$",
        description=f"Payment method: {' or '.join(sorted(PAYMENT_METHODS))}",
    )


class EndSessionRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)


class SessionHistoryItem(BaseModel):
    session_id: str
    lot_id: str
    lot_name: str
    start_time: Optional[str]
    end_time: Optional[str]
    duration_minutes: int
    amount_charged: float
    status: str


class SessionHistoryResponse(BaseModel):
    total_sessions: int
    sessions: List[SessionHistoryItem]


class PricingBreakdownResponse(BaseModel):
    session_id: str
    lot_id: str
    entry_price: float = 0.0
    base_price: float = 0.0
    price_multiplier: float = 0.0
    price_cap: float = 0.0
    final_price: float = 0.0
    duration_hours: float = 0.0
    amount_charged: float = 0.0
    formula: str = (
        "entry_price × min(duration_hours,1) + "
        "final_price × max(duration_hours-1,0)"
    )
    breakdown: str = ""
    layers_activated: Optional[List[str]] = None


class SessionDetailResponse(BaseModel):
    session_id: str
    lot_id: str
    slot: int
    driver_id: str
    status: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_minutes: Optional[int] = None
    entry_price: float = 0.0
    final_price: float = 0.0
    amount_charged: float = 0.0
    blockchain_ref: Optional[str] = None
    payment_method: str = "card"


class ActiveSessionItem(BaseModel):
    session_id: str
    slot: int
    start_time: Optional[str] = None
    entry_price: float


class ActiveSessionsResponse(BaseModel):
    lot_id: str
    active_count: int
    sessions: List[ActiveSessionItem]


class SessionStartResponse(BaseModel):
    session_id: str
    lot_id: str
    driver_id: str
    slot: int
    start_time: str
    predicted_occupancy: float
    price_at_entry: float
    base_price: float
    price_multiplier: float
    blockchain_ref: Optional[str] = None
    iot_consensus: float
    iot_fp_rate: float
    weather_factor: float
    digital_twin: dict
    layers_activated: List[str]


class SessionEndResponse(BaseModel):
    session_id: str
    lot_id: str
    driver_id: str
    duration_hours: float
    entry_price: float
    final_price: float
    amount_charged: float
    blockchain_ref: Optional[str] = None
    end_time: str
    layers_activated: List[str]
    duration_minutes: int
    total_cost: float
    slot: int = 0
    slot_label: str = ""
    deposit_refund: float = 0.0


class SessionReceiptResponse(BaseModel):
    session_id: str
    lot_id: str
    driver_id: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_minutes: int = 0
    duration_hours: float = 0.0
    entry_price: float = 0.0
    final_price: float = 0.0
    amount_charged: float = 0.0
    breakdown: str = (
        "entry_price × min(duration_hours,1) + "
        "final_price × max(duration_hours-1,0)"
    )
    blockchain_ref: Optional[str] = None
    payment_method: str = "card"
