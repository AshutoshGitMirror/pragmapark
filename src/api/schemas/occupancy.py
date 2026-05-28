from typing import Optional

from pydantic import BaseModel, Field


class OccupancyHistoryItem(BaseModel):
    timestamp: Optional[str] = None
    occupancy_rate: float
    price: float
    net_flux: float = 0.0


class IngestOccupancyRequest(BaseModel):
    lot_id: str = Field(min_length=1, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    occupied_slots: int = Field(ge=0, le=100000)
    total_slots: int = Field(ge=1, le=100000)
    net_flux: float = 0.0
    sensor_id: str = Field(default="", max_length=100)


class IngestOccupancyResponse(BaseModel):
    status: str
    lot_id: str
    occupancy_rate: float
