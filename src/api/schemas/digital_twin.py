from typing import Optional

from pydantic import BaseModel, Field


class ScenarioRequest(BaseModel):
    zone_id: str = Field("zone_0", max_length=50)
    occupancy_rate: float = Field(0.5, ge=0, le=1)
    price: float = Field(10.0, ge=0, le=100000)
    total_slots: int = Field(500, ge=1, le=100000)
    scenario_name: Optional[str] = Field(None, max_length=100)


class ScenarioPipelineRequest(BaseModel):
    scenario_type: str = Field("zone_closure", max_length=100)
    zone_id: str = Field("zone_0", max_length=50)


class GenerateScenarioRequest(BaseModel):
    base_occupancy: float = Field(0.5, ge=0, le=1)
    base_price: float = Field(10.0, ge=0, le=100000)


class TrainGeneratorRequest(BaseModel):
    epochs: int = Field(200, ge=1, le=1000)


class ScenarioListItem(BaseModel):
    name: str
    description: str
    occupancy_shift: int = 0
    price_adjust: float = 0.0


class ScenarioRunResponse(BaseModel):
    base_state: dict
    results: list
    comparisons: list


class GenerateScenarioResponse(BaseModel):
    synthetic_occupancy: float
    synthetic_price: float
    congestion_score: float


class TrainGeneratorResponse(BaseModel):
    status: str
    epochs: int
    final_loss: Optional[list[float]] = None


class ScenarioPipelineResponse(BaseModel):
    scenario: str
    zone_id: str
    result: Optional[dict] = None
    all_scenarios: list
    comparisons: list


class PipelineStatusResponse(BaseModel):
    ml_models: dict
    rl_agent: bool
    blockchain: dict
    digital_twin: dict
    actuator: dict
