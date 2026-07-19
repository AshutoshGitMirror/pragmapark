from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class RoutePoint(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class RouteRequest(BaseModel):
    model_config = {"extra": "forbid"}
    origin: RoutePoint
    destination: RoutePoint
    mode: Literal["drive", "walk"] = "drive"


class RouteResponse(BaseModel):
    found: bool
    distance_m: float = 0.0
    duration_s: float = 0.0
    geometry: List[RoutePoint] = []
    message: Optional[str] = None
