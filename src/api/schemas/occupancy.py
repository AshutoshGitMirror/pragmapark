from typing import List, Optional

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


class IngestSensorReadingsRequest(BaseModel):
    lot_id: str = Field(min_length=1, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    ultrasonic_readings: Optional[List[bool]] = Field(default=None, max_length=1000, description="Ground truth from ultrasonic sensors per slot")
    vision_readings: Optional[List[bool]] = Field(default=None, max_length=1000, description="Detection from vision sensors per slot")
    weather_factor: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    net_flux: Optional[float] = 0.0
    total_slots: Optional[int] = Field(default=None, ge=1, le=1000, description="Optional slot capacity for simulator fallback")


class IngestSensorReadingsResponse(BaseModel):
    status: str
    lot_id: str
    occupancy_rate: float
    false_positive_rate: float
    fused_count: int
    weather_factor: float = 0.0
