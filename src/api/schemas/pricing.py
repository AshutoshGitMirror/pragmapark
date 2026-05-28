from typing import List

from pydantic import BaseModel, ConfigDict, Field


class PricingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    predicted_occupancy: float = Field(ge=0, le=1)
    current_price: float = Field(ge=0, le=100000)


class PricingResponse(BaseModel):
    price_multiplier: float
    new_price: float
    is_hike: bool


class ZonePricingResponse(BaseModel):
    zone_id: str
    base_price: float
    price_range: List[float]
    currency: str
    dynamic_pricing: bool
