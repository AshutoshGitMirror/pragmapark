from pydantic import BaseModel, Field
from typing import List, Optional, Dict


class PredictionRequest(BaseModel):
    occupied_slots: float
    total_slots: float
    occ_lag_15m: float
    occ_lag_1h: float
    net_flux: float
    hour: int = Field(ge=0, le=23)


class PredictionResponse(BaseModel):
    rf_prediction: float
    xgb_prediction: float
    ensemble_prediction: float
    mae: Optional[float] = None


class PricingRequest(BaseModel):
    predicted_occupancy: float = Field(ge=0, le=1)
    current_price: float = Field(ge=0, le=100)


class PricingResponse(BaseModel):
    price_multiplier: float
    new_price: float
    is_hike: bool


class OccupancyResponse(BaseModel):
    lot_id: str
    occupancy_rate: float
    total_slots: int
    occupied_slots: float
    timestamp: str
    congestion_level: str


class BlockchainStatusResponse(BaseModel):
    chain_length: int
    chain_valid: bool
    last_block_hash: str
    total_transactions: int


class TransactionRequest(BaseModel):
    driver_id: str
    lot_id: str
    action: str
    price: float
    duration_minutes: int


class TransactionResponse(BaseModel):
    tx_hash: str
    block_index: int
    status: str


class ScenarioRequest(BaseModel):
    zone_id: str
    occupancy_rate: float = 0.5
    price: float = 10.0
    total_slots: int = 500


class ScenarioResponse(BaseModel):
    scenario: str
    description: str
    impacts: Dict
    result: Dict


class MARLRequest(BaseModel):
    num_zones: int = 4
    episodes: int = 200


class MARLResponse(BaseModel):
    status: str
    episode_rewards: List[float]
    validation: Dict
