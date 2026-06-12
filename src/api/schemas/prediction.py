from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    occupied_slots: float = Field(ge=0)
    total_slots: float = Field(ge=1)
    occ_lag_15m: float = Field(ge=0)
    occ_lag_1h: float = Field(ge=0)
    net_flux: float
    hour: int = Field(default=12, ge=0, le=23)
    dow: int = Field(
        default=0, ge=0, le=6, description="Day of week (0=Monday, 6=Sunday)"
    )


class PredictionResponse(BaseModel):
    rf_prediction: float
    xgb_prediction: float
    ensemble_prediction: float
    mae: Optional[float] = None


class ModelHealthResponse(BaseModel):
    rf_loaded: bool
    xgb_loaded: bool
    status: str
