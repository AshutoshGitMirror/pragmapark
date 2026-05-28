from typing import List, Optional

from pydantic import BaseModel

from .occupancy import OccupancyHistoryItem


class DriverLotDetail(BaseModel):
    lot_id: str
    name: str
    address: Optional[str] = ""
    total_slots: int
    base_price: float
    latitude: Optional[float] = 0.0
    longitude: Optional[float] = 0.0
    predicted_occupancy: float
    current_price: float
    available_spots: int
    available_handicap: int = 0
    available_ev: int = 0
    available_regular: int = 0
    recent_occupancy: List[OccupancyHistoryItem]


class DriverLotSearchItem(BaseModel):
    lot_id: str
    name: str
    address: str
    city: str
    total_slots: int
    base_price: float
    predicted_occupancy: float
    available_spots: int
    dynamic_price: float
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    available_handicap: int = 0
    available_ev: int = 0
    available_regular: int = 0


class DriverLotsResponse(BaseModel):
    lots: List[DriverLotSearchItem]
