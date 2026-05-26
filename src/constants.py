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

EXPECTED_FEATURE_COLS = [
    "occupied_slots", "total_slots", "occ_lag_15m", "occ_lag_1h", "net_flux",
    "pe_arrival_rate", "pe_departure_rate", "pe_turnover", "pe_anomaly", "pe_change_point",
    "hour_sin", "hour_cos", "hour_sq",
    "dow_sin", "dow_cos", "is_weekend",
    "occ_roll_mean_3h", "occ_roll_std_3h", "occ_acceleration",
]


def cyclical_time_features(dt: Optional[datetime] = None) -> dict:
    if dt is None:
        dt = datetime.now(timezone.utc)
    hour = dt.hour
    dow = dt.weekday()
    return {
        "hour_sin": np.sin(2 * np.pi * hour / 24),
        "hour_cos": np.cos(2 * np.pi * hour / 24),
        "hour_sq": (hour - 12) / 12,
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
