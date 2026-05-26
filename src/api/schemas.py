from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LogoutResponse(BaseModel):
    message: str = "logged_out"

class DashboardResponse(BaseModel):
    total_lots: int
    total_users: int
    total_revenue: float
    total_transactions: int
    system_occupancy: float

class SystemHealthResponse(BaseModel):
    status: str
    transactions_last_hour: int
    occupancy_updates_last_5min: int
    layers: dict


class AuthUser(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: str
    organization: str = ""


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUser


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)  # password min 8 chars; hashed output fits in String(255)
    full_name: str = Field(default="", max_length=255)
    organization: str = Field(default="", max_length=255)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    occupied_slots: float = Field(ge=0)
    total_slots: float = Field(ge=1)
    occ_lag_15m: float = Field(ge=0)
    occ_lag_1h: float = Field(ge=0)
    net_flux: float
    hour: int = Field(default=12, ge=0, le=23)


class PredictionResponse(BaseModel):
    rf_prediction: float
    xgb_prediction: float
    ensemble_prediction: float
    mae: Optional[float] = None


class PricingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    predicted_occupancy: float = Field(ge=0, le=1)
    current_price: float = Field(ge=0, le=100000)


class PricingResponse(BaseModel):
    price_multiplier: float
    new_price: float
    is_hike: bool


class OccupancyHistoryItem(BaseModel):
    timestamp: Optional[str] = None
    occupancy_rate: float
    price: float
    net_flux: float = 0.0


class LotSummary(BaseModel):
    lot_id: str
    name: str
    address: str = ""
    city: str = ""
    total_slots: int
    latitude: float = 0.0
    longitude: float = 0.0
    base_price: float
    price_cap: float
    current_occupancy: float = 0.0
    current_price: float


class LotDetail(BaseModel):
    lot_id: str
    name: str
    address: str = ""
    city: str = ""
    total_slots: int
    latitude: float = 0.0
    longitude: float = 0.0
    base_price: float
    price_cap: float
    history: List[OccupancyHistoryItem]


class LotCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lot_id: str = Field(min_length=1, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=255)
    address: str = ""
    city: str = ""
    total_slots: int = Field(ge=1, le=100000)
    latitude: float = 0.0
    longitude: float = 0.0
    base_price: float = Field(ge=0, le=100000)
    price_cap: float = Field(default=200.0, ge=0, le=100000)


class LotUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Optional[str] = None
    address: Optional[str] = None
    total_slots: Optional[int] = Field(None, ge=1, le=100000)
    base_price: Optional[float] = Field(None, ge=0, le=100000)
    price_cap: Optional[float] = Field(None, ge=0, le=100000)


class LotCreateResponse(BaseModel):
    status: str
    lot_id: str


class LotUpdateResponse(BaseModel):
    status: str
    lot_id: str
    base_price: float
    price_cap: float


class LotOccupancyResponse(BaseModel):
    lot_id: str
    name: str
    current_occupancy: float
    current_price: float
    records: List[OccupancyHistoryItem]


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


class BlockchainStatusResponse(BaseModel):
    chain_length: int
    chain_valid: bool
    last_block_hash: str
    pending_transactions: int


class TransactionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    driver_id: str = Field(min_length=1, max_length=100)
    lot_id: str = Field(min_length=1, max_length=50)
    action: str = Field(min_length=1, max_length=50)
    price: float = Field(default=0.0, ge=0)  # NOTE: maps to ORM Transaction.amount
    duration_minutes: int = Field(default=60, ge=1, le=100000)


class TransactionResponse(BaseModel):
    tx_hash: str
    block_index: int
    status: str


class PoolCreateRequest(BaseModel):
    pool_id: str = Field(min_length=1, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    total_spots: int = Field(ge=1, le=100000)
    owner: str = Field("city", max_length=100)


class ScenarioRequest(BaseModel):
    zone_id: str = Field("zone_0", max_length=50)
    occupancy_rate: float = Field(0.5, ge=0, le=1)
    price: float = Field(10.0, ge=0, le=100000)
    total_slots: int = Field(500, ge=1, le=100000)


class ScenarioPipelineRequest(BaseModel):
    scenario_type: str = Field("zone_closure", max_length=100)
    zone_id: str = Field("zone_0", max_length=50)


class GenerateScenarioRequest(BaseModel):
    base_occupancy: float = Field(0.5, ge=0, le=1)
    base_price: float = Field(10.0, ge=0, le=100000)


class TrainGeneratorRequest(BaseModel):
    epochs: int = Field(200, ge=1, le=1000)


class MARLRequest(BaseModel):
    num_zones: int = Field(4, ge=1, le=100)
    episodes: int = Field(200, ge=1, le=10000)


class MARLResponse(BaseModel):
    status: str
    num_zones: int
    episodes: int
    final_reward: float
    validation: Dict


class StartSessionRequest(BaseModel):
    lot_id: str = Field(min_length=1, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    slot: int = Field(default=0, ge=0, le=100000)
    force: bool = Field(default=False, description="Force-start: ends any existing active session first")
    flat_rate: bool = Field(default=False, description="Use lot base_price instead of dynamic pricing")
    payment_method: str = Field(default="card", pattern=r"^(card|cash)$", description="card or cash")


class EndSessionRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)


class SessionHistoryItem(BaseModel):
    session_id: str
    lot_id: str
    lot_name: str
    start_time: Optional[str]
    end_time: Optional[str]
    duration_minutes: int
    amount_charged: float
    status: str


class SessionHistoryResponse(BaseModel):
    total_sessions: int
    sessions: List[SessionHistoryItem]


class PricingBreakdownResponse(BaseModel):
    session_id: str
    lot_id: str
    entry_price: float = 0.0
    base_price: float = 0.0
    price_multiplier: float = 0.0
    price_cap: float = 0.0
    final_price: float = 0.0
    duration_hours: float = 0.0
    amount_charged: float = 0.0
    formula: str = "entry_price × min(duration_hours,1) + final_price × max(duration_hours-1,0)"
    breakdown: str = ""
    layers_activated: Optional[List[str]] = None


class PaymentConfirmRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    idempotency_key: str = Field(default="", max_length=64)


class PaymentHistoryItem(BaseModel):
    tx_hash: str
    lot_id: str
    amount: float
    timestamp: Optional[str]
    status: str


class PaymentHistoryResponse(BaseModel):
    total_payments: int
    payments: List[PaymentHistoryItem]


class RevenueCumulativeResponse(BaseModel):
    total_revenue: float = 0.0
    total_sessions: int = 0
    total_lots: int = 0
    total_drivers: int = 0
    avg_revenue_per_session: float = 0.0
    avg_revenue_per_lot: float = 0.0

class RevenueOverviewItem(BaseModel):
    lot_id: str
    name: str
    total_revenue: float
    total_transactions: int
    avg_daily_revenue: float


class RevenueOverviewResponse(BaseModel):
    total_revenue: float
    total_transactions: int
    daily: List[RevenueOverviewItem]


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


class MineBlockResponse(BaseModel):
    block_index: int
    hash: str
    transactions: int
    nonce: int
    timestamp: float


class PoolDetailResponse(BaseModel):
    pool_id: str
    total_spots: int
    owner: str
    available: int
    active_allocations: int
    total_revenue: float
    pool_revenue: float


class PoolCreateResponse(BaseModel):
    status: str
    pool_id: str
    total_spots: int


class ScenarioListItem(BaseModel):
    name: str
    description: str


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


class MARLStatusResponse(BaseModel):
    status: str
    num_zones: Optional[int] = None
    episodes_completed: Optional[int] = None
    mean_reward: Optional[float] = None
    validation: Optional[dict] = None


class ZonePricingResponse(BaseModel):
    zone_id: str
    base_price: float
    price_range: List[float]
    currency: str
    dynamic_pricing: bool


class ModelHealthResponse(BaseModel):
    rf_loaded: bool
    xgb_loaded: bool
    status: str


class SessionDetailResponse(BaseModel):
    session_id: str
    lot_id: str
    slot: int
    driver_id: str
    status: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_minutes: Optional[int] = None
    entry_price: float = 0.0
    final_price: float = 0.0
    amount_charged: float = 0.0
    blockchain_ref: Optional[str] = None
    payment_method: str = "card"

class ActiveSessionItem(BaseModel):
    session_id: str
    slot: int
    start_time: Optional[str] = None
    entry_price: float


class ActiveSessionsResponse(BaseModel):
    lot_id: str
    active_count: int
    sessions: List[ActiveSessionItem]


class TransactionHistoryItem(BaseModel):
    tx_hash: str
    lot_id: str
    driver_id: str
    action: str
    amount: float
    duration_minutes: int
    status: str
    timestamp: Optional[str] = None


class PipelineStatusResponse(BaseModel):
    ml_models: dict
    rl_agent: bool
    blockchain: dict
    digital_twin: dict
    actuator: dict

class ScenarioPipelineResponse(BaseModel):
    scenario: str
    zone_id: str
    result: Optional[dict] = None
    all_scenarios: list
    comparisons: list

class SlotResponse(BaseModel):
    id: int
    lot_id: str
    slot_index: int
    row_label: str
    position: int
    slot_type: str
    state: str = "available"
    current_price: float = 0.0
    probability: float = 0.0
    probability_adjusted_price: float = 0.0
    base_modifier_score: float = 0.0

class SlotProbabilityResponse(BaseModel):
    slot_id: int
    slot_label: str
    probability: float
    current_state: str
    current_price: float

class ReserveSlotRequest(BaseModel):
    lot_id: str = Field(min_length=1, max_length=50)
    slot_index: int = Field(ge=0)
    target_time: Optional[str] = None
    idempotency_key: Optional[str] = None

class ReserveSlotResponse(BaseModel):
    reservation_id: int
    slot_label: str
    slot_id: int
    probability: float
    expires_at: str
    status: str

class ReleaseSlotRequest(BaseModel):
    slot_id: int
    reservation_id: int

class SlotsListResponse(BaseModel):
    lot_id: str
    total_slots: int
    available: int
    reserved: int
    occupied: int
    prebooked: int = 0
    slots: List[SlotResponse]

class MicroZoneResponse(BaseModel):
    id: int
    name: str
    slot_count: int
    available: int
    occupancy_rate: float

class SessionStartResponse(BaseModel):
    session_id: str
    lot_id: str
    driver_id: str
    slot: int
    start_time: str
    predicted_occupancy: float
    price_at_entry: float
    base_price: float
    price_multiplier: float
    blockchain_ref: Optional[str] = None
    iot_consensus: float
    iot_fp_rate: float
    weather_factor: float
    digital_twin: dict
    layers_activated: List[str]

class SessionEndResponse(BaseModel):
    session_id: str
    lot_id: str
    driver_id: str
    duration_hours: float
    entry_price: float
    final_price: float
    amount_charged: float
    blockchain_ref: Optional[str] = None
    end_time: str
    layers_activated: List[str]
    duration_minutes: int
    total_cost: float

class PaymentConfirmResponse(BaseModel):
    session_id: str
    tx_hash: str = ""
    blockchain_ref: str = ""
    amount: float = 0.0
    ledger_blocks: int = 0
    already_paid: bool = False

class ReleaseSlotResponse(BaseModel):
    status: str
    slot_id: int

class SessionReceiptResponse(BaseModel):
    session_id: str
    lot_id: str
    driver_id: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_minutes: int = 0
    duration_hours: float = 0.0
    entry_price: float = 0.0
    final_price: float = 0.0
    amount_charged: float = 0.0
    breakdown: str = "entry_price × min(duration_hours,1) + final_price × max(duration_hours-1,0)"
    blockchain_ref: Optional[str] = None
    payment_method: str = "card"

class PrebookSlotItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slot_index: int = Field(ge=1)
    priority: Optional[int] = Field(None, ge=0, le=10)

class PrebookRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lot_id: str = Field(min_length=1, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    slots: List[PrebookSlotItem] = Field(min_length=1, max_length=3)
    target_time: str = Field(min_length=1)
    idempotency_key: Optional[str] = Field(None, max_length=64)

class PrebookResponse(BaseModel):
    prebook_id: str
    lot_id: str
    assigned_slot_index: int
    slot_label: str = ""
    probability: float = 0.0
    price_at_booking: float = 0.0
    expires_at: str = ""
    status: str = "active"
    fallback_order: Optional[List[int]] = None

class ConfirmPrebookRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prebook_id: str = Field(min_length=1, max_length=64)

class ConfirmPrebookResponse(BaseModel):
    session_id: str = ""
    prebook_id: str
    slot_id: int = 0
    slot_index: int = 0
    slot_label: str = ""
    final_price: float = 0.0
    status: str = ""

class SeedSlotsResponse(BaseModel):
    status: str
    count: int = 0
    total_slots: int = 0
