from typing import List, Optional

from pydantic import BaseModel

from .occupancy import OccupancyHistoryItem


# All numeric fields are Optional-with-default so a None produced by nullable
# DB columns / predict / pricing paths degrades to a sane value instead of
# raising an unlogged ResponseValidationError (HTTP 500). See A110.
class DriverLotDetail(BaseModel):
    lot_id: str
    name: str
    address: Optional[str] = ""
    city: str = ""
    total_slots: Optional[int] = 0
    base_price: Optional[float] = 0.0
    latitude: Optional[float] = 0.0
    longitude: Optional[float] = 0.0
    predicted_occupancy: Optional[float] = 0.0
    current_price: Optional[float] = 0.0
    available_spots: Optional[int] = 0
    available_handicap: int = 0
    available_ev: int = 0
    available_regular: int = 0
    recent_occupancy: List[OccupancyHistoryItem]


class DriverLotSearchItem(BaseModel):
    lot_id: str
    name: str
    address: str = ""
    city: str = ""
    total_slots: Optional[int] = 0
    base_price: Optional[float] = 0.0
    predicted_occupancy: Optional[float] = 0.0
    available_spots: Optional[int] = 0
    dynamic_price: Optional[float] = 0.0
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    available_handicap: int = 0
    available_ev: int = 0
    available_regular: int = 0


class DriverLotsResponse(BaseModel):
    lots: List[DriverLotSearchItem]
