from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SlotResponse(BaseModel):
    id: int
    lot_id: str
    slot_index: int
    row_label: str
    position: int
    slot_type: str
    state: str = "available"
    current_price: float = 0.0
    probability: float = 0.0
    probability_adjusted_price: float = 0.0
    base_modifier_score: float = 0.0


class SlotProbabilityResponse(BaseModel):
    slot_id: int
    slot_label: str
    probability: float
    current_state: str
    current_price: float


class ReserveSlotRequest(BaseModel):
    lot_id: str = Field(min_length=1, max_length=50)
    slot_index: int = Field(ge=1, description="1-based slot index in the lot")
    target_time: Optional[str] = None
    idempotency_key: Optional[str] = None


class ReserveSlotResponse(BaseModel):
    reservation_id: int
    slot_label: str
    slot_id: int
    probability: float
    expires_at: str
    status: str


class ReleaseSlotRequest(BaseModel):
    slot_id: int
    reservation_id: int


class ReleaseSlotResponse(BaseModel):
    status: str
    slot_id: int


class SlotsListResponse(BaseModel):
    lot_id: str
    total_slots: int
    available: int
    reserved: int
    occupied: int
    prebooked: int = 0
    slots: List[SlotResponse]


class MicroZoneResponse(BaseModel):
    id: int
    name: str
    slot_count: int
    available: int
    occupancy_rate: float


class SeedSlotsResponse(BaseModel):
    status: str
    count: int = 0
    total_slots: int = 0


class PrebookSlotItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slot_index: int = Field(ge=1)
    priority: Optional[int] = Field(None, ge=0, le=10)


class PrebookRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lot_id: str = Field(
        min_length=1, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$"
    )
    slots: List[PrebookSlotItem] = Field(min_length=1, max_length=3)
    target_time: str = Field(min_length=1)
    idempotency_key: Optional[str] = Field(None, max_length=64)


class PrebookResponse(BaseModel):
    prebook_id: str
    lot_id: str
    assigned_slot_index: int
    slot_index: int = 0
    slot_label: str = ""
    probability: float = 0.0
    price_at_booking: float = 0.0
    booking_fee: float = 0.0
    deposit: float = 0.0
    expires_at: str = ""
    status: str = "active"
    fallback_order: Optional[List[int]] = None


class ConfirmPrebookRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prebook_id: str = Field(min_length=1, max_length=64)


class ConfirmPrebookResponse(BaseModel):
    session_id: str = ""
    prebook_id: str
    slot_id: int = 0
    slot_index: int = 0
    slot_label: str = ""
    final_price: float = 0.0
    status: str = ""
    message: str = ""


class CancelPrebookResponse(BaseModel):
    status: str
    prebook_id: str
    refund_amount: float = 0.0
    message: str = ""


class PrebookListItem(BaseModel):
    prebook_id: str
    lot_id: str
    lot_name: str
    driver_id: str
    slot_index: int
    slot_label: str
    target_time: Optional[str] = None
    expires_at: Optional[str] = None
    probability_given: Optional[float] = None
    price_at_booking: Optional[float] = None
    status: str
    booking_fee: Optional[float] = None
    deposit: Optional[float] = None
    deposit_refunded: bool = False
    created_at: Optional[str] = None


class PrebookListResponse(BaseModel):
    prebooks: list[PrebookListItem]
