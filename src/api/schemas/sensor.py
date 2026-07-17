from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field


class SensorCreateRequest(BaseModel):
    lot_id: str = Field(
        min_length=1, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$"
    )
    label: str = Field(default="", max_length=255)


class SensorUpdateRequest(BaseModel):
    label: Optional[str] = Field(default=None, max_length=255)
    active: Optional[bool] = None


class SensorResponse(BaseModel):
    sensor_id: str
    lot_id: str
    label: str
    owner_id: int
    active: bool
    created_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None


class SensorCreateResponse(SensorResponse):
    # Returned exactly once, at creation. Store it securely.
    api_key: str


class SensorRotateResponse(BaseModel):
    sensor_id: str
    lot_id: str
    # New plaintext key, returned once. Old key is invalidated immediately.
    api_key: str
