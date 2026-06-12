from typing import Optional
import numpy as np
from datetime import datetime, timezone

RF_WEIGHT = 0.4
XGB_WEIGHT = 0.6

HIGH_OCCUPANCY_THRESHOLD = 0.8
LOW_OCCUPANCY_THRESHOLD = 0.4
HIGH_OCC_MULTIPLIER = 0.15
LOW_OCC_MULTIPLIER = -0.1
NEUTRAL_MULTIPLIER = 0.0
PRICE_FLOOR_RATIO = 0.3

ACTION_MIN = -0.2
ACTION_MAX = 0.5
PRICE_MIN = 5.0
PRICE_MAX = 50.0

DEFAULT_CAPACITY = 500

CONGESTION_HIGH = 0.85
CONGESTION_MODERATE = 0.70
DEFAULT_OCCUPANCY = 0.5
LAG_15M_DECAY = 0.95
LAG_1H_DECAY = 0.85

SENSORS_PER_LOT_DIVISOR = 50
MIN_SENSORS = 5

DATA_RETENTION_DAYS = 90

# Rate limiting
GLOBAL_RATE_LIMIT_CALLS = 200
GLOBAL_RATE_LIMIT_WINDOW = 60.0
# DB retries
DB_INIT_MAX_RETRIES = 5
# Periodic task intervals (seconds)
MINER_INTERVAL_S = 300
CLEANUP_INTERVAL_S = 3600
OUTBOX_INTERVAL_S = 60
INGEST_INTERVAL_S = 60
INGEST_RETRIES = 3
# Session defaults
SESSION_STALE_HOURS = 24
MIN_RECORDS_FOR_FEATURES = 5
DEFAULT_BASE_PRICE = 10.0
DEFAULT_PRICE_CAP = 200.0
DEFAULT_TOTAL_SLOTS = 500
FREE_GRACE_MINUTES = 15
MIN_CHARGE_AMOUNT = 1.0
# Wallet deduction constants (Option D: Deposit + Auto-Refund)
BOOKING_FEE = 2.0  # Non-refundable fee on prebook
DEPOSIT_RATE = 1.0  # 1 hour of base price as refundable deposit
ADMIN_FEE_RATE = 0.1  # 10% admin fee on early cancel
# IoT simulation params
IOT_WEATHER_MAX = 0.3
IOT_GROUND_TRUTH_PROB = 0.5
# Slot type distribution thresholds
SLOT_TYPE_REGULAR_MAX = 0.05
SLOT_TYPE_HANDICAP_MAX = 0.10
SLOT_TYPE_EV_MAX = 0.25
SLOT_TYPE_COVERED_MAX = 0.30
# PREMIUM distribution threshold (slot type bonus is 15%)
SLOT_TYPE_PREMIUM_MAX = 0.35
# Prebook scoring
PREBOOK_SCORE_PROB_WEIGHT = 10
PREBOOK_SCORE_PRICE_PENALTY = 0.05
PREBOOK_DEFAULT_PRIORITY = 999
# Slot-level prediction constants
PRIOR_PROBABILITY = 0.5
LONG_HORIZON_THRESHOLD_S = 3600
LONG_HORIZON_PROBABILITY = 0.5
PROBABILITY_FLOOR = 0.1
RESERVED_PROBABILITY = 0.9
RESERVED_DECAY_MULTIPLIER = 2.0
# Micro pricing formula
PROB_MULT_MIN = 0.7
PROB_MULT_RANGE = 0.6
# Six-layer names (used in session responses)
LAYER_NAMES = ["iot", "ml", "blockchain", "rl", "digital_twin", "actuator"]

# --- Status vocabularies (single source of truth) ---

# ParkingSession statuses
SESSION_RUNNING = "running"
SESSION_PENDING_SETTLEMENT = "pending_settlement"
SESSION_SETTLED = "settled"
SESSION_CANCELLED = "cancelled"
SESSION_STATUSES = {
    SESSION_RUNNING,
    SESSION_PENDING_SETTLEMENT,
    SESSION_SETTLED,
    SESSION_CANCELLED,
}

# Transaction statuses
TX_PENDING = "pending"
TX_COMPLETED = "completed"
TX_FAILED = "failed"
TX_STATUSES = {TX_PENDING, TX_COMPLETED, TX_FAILED}

# Transaction actions
TX_ACTION_SESSION_FEE = "session_fee"
TX_ACTION_PAYMENT = "payment"
TX_ACTION_REFUND = "refund"
TX_ACTION_DEPOSIT = "deposit"
TX_ACTION_BOOKING_FEE = "booking_fee"
TX_ACTIONS = {
    TX_ACTION_SESSION_FEE,
    TX_ACTION_PAYMENT,
    TX_ACTION_REFUND,
    TX_ACTION_DEPOSIT,
    TX_ACTION_BOOKING_FEE,
}

# Payment methods
PAYMENT_METHODS = {"card", "cash"}

# Slot reservation / prebook statuses
RESERVATION_ACTIVE = "active"
RESERVATION_CONFIRMED = "confirmed"
RESERVATION_USED = "used"
RESERVATION_CANCELLED = "cancelled"
RESERVATION_EXPIRED = "expired"
RESERVATION_REFUNDED = "refunded"
RESERVATION_NO_SHOW = "no_show"
RESERVATION_STATUSES = {
    RESERVATION_ACTIVE,
    RESERVATION_CONFIRMED,
    RESERVATION_USED,
    RESERVATION_CANCELLED,
    RESERVATION_EXPIRED,
    RESERVATION_REFUNDED,
    RESERVATION_NO_SHOW,
}

# Ledger outbox statuses
OUTBOX_PENDING = "pending"
OUTBOX_DELIVERED = "delivered"
OUTBOX_FAILED = "failed"
OUTBOX_STATUSES = {OUTBOX_PENDING, OUTBOX_DELIVERED, OUTBOX_FAILED}

# Blockchain allocation statuses
ALLOC_RESERVED = "reserved"
ALLOC_CONFIRMED = "confirmed"
ALLOC_RELEASED = "released"
ALLOC_STATUSES = {ALLOC_RESERVED, ALLOC_CONFIRMED, ALLOC_RELEASED}
# RL environment defaults
RL_DEFAULT_VEHICLE_RATIO = 0.5
RL_DEFAULT_BASE_PRICE = 10.0
# Actuator congestion thresholds (already partially defined as
# CONGESTION_HIGH/MODERATE)
CONGESTION_LOW = 0.50
CONGESTION_LEVELS = {"normal", "moderate", "high", "critical"}


EXPECTED_FEATURE_COLS = [
    "occupied_slots",
    "total_slots",
    "occ_lag_15m",
    "occ_lag_1h",
    "pe_net_flux",
    "pe_arrival_rate",
    "pe_departure_rate",
    "pe_turnover",
    "pe_anomaly",
    "pe_change_point",
    "hour_sin",
    "hour_cos",
    "hour_sq",
    "dow_sin",
    "dow_cos",
    "is_weekend",
    "occ_roll_mean_3h",
    "occ_roll_std_3h",
    "occ_acceleration",
]


def cyclical_time_features(dt: Optional[datetime] = None) -> dict:
    if dt is None:
        dt = datetime.now(timezone.utc)
    hour = dt.hour
    dow = dt.weekday()
    return {
        "hour_sin": np.sin(2 * np.pi * hour / 24),
        "hour_cos": np.cos(2 * np.pi * hour / 24),
        "hour_sq": (hour - 12) ** 2 / 144,
        "dow_sin": np.sin(2 * np.pi * dow / 7),
        "dow_cos": np.cos(2 * np.pi * dow / 7),
        "is_weekend": 1.0 if dow >= 5 else 0.0,
    }


def heuristic_price_multiplier(occupancy: float) -> float:
    if occupancy > HIGH_OCCUPANCY_THRESHOLD:
        return HIGH_OCC_MULTIPLIER
    elif occupancy < LOW_OCCUPANCY_THRESHOLD:
        return LOW_OCC_MULTIPLIER
    return NEUTRAL_MULTIPLIER


# --- Holiday calendar (US + UK major holidays) ---
# Month/day tuples — simple, no external deps
HOLIDAYS = {
    (1, 1),  # New Year's Day
    (1, 15),  # MLK Day (approx, 3rd Mon Jan)
    (2, 14),  # Valentine's Day
    (2, 22),  # Presidents' Day (approx, 3rd Mon Feb)
    (5, 25),  # Memorial Day (approx, last Mon May)
    (7, 4),  # Independence Day
    (9, 1),  # Labor Day (approx, 1st Mon Sep)
    (10, 31),  # Halloween
    (11, 11),  # Remembrance Day / Veterans Day
    (11, 24),  # Thanksgiving (approx, 4th Thu Nov)
    (12, 25),  # Christmas
    (12, 26),  # Boxing Day
    (12, 31),  # New Year's Eve
}


def is_holiday(dt: datetime) -> bool:
    return (dt.month, dt.day) in HOLIDAYS


# --- Simulation / demo mode ---
DEMO_SPEED_OPTIONS = [1, 10, 60]
DEFAULT_DEMO_SPEED = 1
DRIVER_DEFAULT_BALANCE = 10000.0
HISTORY_DAYS = 30
