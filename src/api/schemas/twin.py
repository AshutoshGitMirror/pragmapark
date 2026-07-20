"""Pydantic schemas for the observation-driven digital twin (P1)."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ObservationCreate(BaseModel):
    lot_id: str
    observed_at: datetime
    occupied_slots: int = Field(ge=0)
    total_slots: int = Field(ge=1)
    arrivals: int = 0
    departures: int = 0
    price: float = 0.0
    sensor_confidence: float = 1.0
    source: str = "iot"
    context: dict[str, Any] = Field(default_factory=dict)


class ObservationOut(BaseModel):
    id: int
    lot_id: str
    observed_at: datetime
    occupancy_rate: float
    occupied_slots: int
    total_slots: int
    price: float
    source: str

    model_config = {"from_attributes": True}


class StateOut(BaseModel):
    id: int
    lot_id: str
    state_at: datetime
    est_occupancy_rate: float
    est_available_slots: int
    est_price: float
    congestion_level: float
    confidence: float
    source_observation_id: Optional[int]

    model_config = {"from_attributes": True}


class ForecastOut(BaseModel):
    id: int
    lot_id: str
    generated_at: datetime
    target_at: datetime
    horizon_minutes: int
    predicted_occupancy_rate: float
    lower_occupancy_rate: Optional[float]
    upper_occupancy_rate: Optional[float]
    model_name: str
    model_version: str
    input_observation_id: Optional[int]
    actual_occupancy_rate: Optional[float]
    error: Optional[float]
    abs_error: Optional[float]

    model_config = {"from_attributes": True}


class ForecastGenerateRequest(BaseModel):
    lot_id: str
    as_of: Optional[datetime] = None
    horizons: list[int] = Field(default_factory=lambda: [15, 60, 1440])


class MetricRow(BaseModel):
    lot_id: str
    model_name: str
    model_version: str
    horizon_minutes: int
    n_evaluated: int
    mae: float
    rmse: float
    bias: float
    interval_coverage: Optional[float]


class EvaluateRequest(BaseModel):
    lot_id: Optional[str] = None


class ScenarioRequest(BaseModel):
    """Request a calibrated (real-data-bounded) scenario run for a lot.

    ``base_state`` supplies the current operating point (occupancy_rate,
    total_slots, price, ...). The returned band is calibrated from REAL
    observed occupancy deltas (never synthetic). The result is a
    recommendation only and never mutates production (principle 8).
    """

    lot_id: str
    scenario: str
    base_state: dict[str, Any] = Field(default_factory=dict)
    horizon_minutes: int = 60
    use_bootstrap: bool = True
    seed: Optional[int] = None


class CalibratedScenarioOut(BaseModel):
    scenario: str
    kind: str
    predicted_occupancy_rate: Optional[float]
    predicted_price: Optional[float]
    lower_occupancy_rate: Optional[float]
    upper_occupancy_rate: Optional[float]
    assumptions: list[str] = Field(default_factory=list)
    uncertainty_note: str = ""
    safety_note: str = ""
    experimental: bool = False
    n_real_samples: int = 0

    model_config = {"from_attributes": True}
