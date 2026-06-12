from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .occupancy import OccupancyHistoryItem


class LotSummary(BaseModel):
    lot_id: str
    name: str
    address: str = ""
    city: str = ""
    total_slots: int
    latitude: float = 0.0
    longitude: float = 0.0
    base_price: float
    price_cap: float
    current_occupancy: float = 0.0
    current_price: float


class LotDetail(BaseModel):
    lot_id: str
    name: str
    address: str = ""
    city: str = ""
    total_slots: int
    latitude: float = 0.0
    longitude: float = 0.0
    base_price: float
    price_cap: float
    history: List[OccupancyHistoryItem]


class LotCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lot_id: str = Field(
        min_length=1, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$"
    )
    name: str = Field(min_length=1, max_length=255)
    address: str = ""
    city: str = ""
    total_slots: int = Field(ge=1, le=100000)
    latitude: float = 0.0
    longitude: float = 0.0
    base_price: float = Field(ge=0, le=100000)
    price_cap: float = Field(default=200.0, ge=0, le=100000)


class LotUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Optional[str] = None
    address: Optional[str] = None
    total_slots: Optional[int] = Field(None, ge=1, le=100000)
    base_price: Optional[float] = Field(None, ge=0, le=100000)
    price_cap: Optional[float] = Field(None, ge=0, le=100000)


class LotCreateResponse(BaseModel):
    status: str
    lot_id: str


class LotUpdateResponse(BaseModel):
    status: str
    lot_id: str
    base_price: float
    price_cap: float


class LotOccupancyResponse(BaseModel):
    lot_id: str
    name: str
    current_occupancy: float
    current_price: float
    records: List[OccupancyHistoryItem]
