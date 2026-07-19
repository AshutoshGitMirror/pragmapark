from typing import Dict, List, Optional
from datetime import date, datetime
from pydantic import BaseModel, Field

from src.constants import VEHICLE_ID_PATTERN


class ResidentProfileCreate(BaseModel):
    model_config = {"extra": "forbid"}
    lot_id: str
    slot_index: int = Field(ge=1)
    permit_type: str = Field(default="monthly", pattern=r"^(monthly|quarterly|yearly|visitor)$")
    start_date: date
    end_date: date
    monthly_rate: Optional[float] = Field(None, ge=0, le=100000)
    registered_vehicle: Optional[str] = Field(None, pattern=VEHICLE_ID_PATTERN)


class ResidentProfileResponse(BaseModel):
    id: int
    user_id: int
    user_email: str
    lot_id: str
    lot_name: str
    slot_index: int
    permit_type: str
    start_date: date
    end_date: date
    monthly_rate: float
    auto_renew: bool
    is_active: bool
    registered_vehicle: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ResidentSlotInfo(BaseModel):
    slot_index: int
    permit_type: str
    is_active: bool
    registered_vehicle: Optional[str] = None


class ResidentialMapSlot(BaseModel):
    """A residential slot placed on the map (standalone home slot or a
    lot-attached permitted slot). Coordinates + geohash spatial_id + share
    status so the admin map can layer residential supply."""

    slot_id: int
    lot_id: Optional[str] = None
    slot_index: int
    latitude: float
    longitude: float
    spatial_id: str
    is_shared: bool
    has_permit: bool
    permit_type: Optional[str] = None
    price_per_hour: Optional[float] = None
    available_from: Optional[str] = None
    available_until: Optional[str] = None
    resident_name: Optional[str] = None
    availability: Optional[Dict[str, object]] = None


class VehicleRegistrationRequest(BaseModel):
    model_config = {"extra": "forbid"}
    vehicle_id: str = Field(..., pattern=VEHICLE_ID_PATTERN)


class ShareListingCreate(BaseModel):
    model_config = {"extra": "forbid"}
    resident_profile_id: Optional[int] = None
    lot_id: Optional[str] = None
    slot_index: Optional[int] = Field(None, ge=1)
    price_per_hour: float = Field(ge=0, le=10000)
    available_from: str = Field(default="00:00", pattern=r"^\d{2}:\d{2}$")
    available_until: str = Field(default="23:59", pattern=r"^\d{2}:\d{2}$")
    max_advance_days: int = Field(default=7, ge=1, le=90)


class ShareListingResponse(BaseModel):
    id: int
    resident_profile_id: int
    resident_name: str
    lot_id: str
    lot_name: str
    slot_index: int
    price_per_hour: float
    available_from: str
    available_until: str
    status: str
    max_advance_days: int
    registered_vehicle: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ShareBookingCreate(BaseModel):
    model_config = {"extra": "forbid"}
    share_listing_id: int
    start_time: datetime
    end_time: datetime


class ShareBookingResponse(BaseModel):
    id: int
    share_listing_id: int
    slot_id: int
    driver_name: str
    lot_name: str
    slot_index: int
    start_time: datetime
    end_time: datetime
    total_cost: float
    platform_fee: float
    owner_payout: float
    status: str
    vehicle_id: Optional[str] = None
    blockchain_ref: Optional[str] = None
    created_at: datetime
