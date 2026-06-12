import logging
import numpy as np
import pandas as pd
from typing import Callable, Optional

from src.features.engine import build_features_from_records as _engine_build

logger = logging.getLogger(__name__)

# pe_ prefix = Parking Event features derived from temporal occupancy patterns
#   pe_arrival_rate     avg positive diff over last 4 samples (15min buckets)
#   pe_departure_rate   avg negative diff over last 4 samples
#   pe_turnover         total absolute diff over last 8 samples
#   pe_anomaly          current occ deviates >2 sigma from expanding mean
#   pe_change_point     CUSUM-based regime-change flag over rolling(8) window
X_COLS: list[str] = [
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


def build_features_from_records(
    records: list, total_slots: int, bucket_dt: object = None
) -> Optional[pd.Series]:
    result = _engine_build(records, total_slots)
    if result is not None:
        missing = [c for c in X_COLS if c not in result.index]
        if missing:
            logger.warning(
                "Feature shape drift: %d missing columns (%s)",
                len(missing),
                missing,
            )
    return result


def safe_predict(
    predict_fn: Callable[[pd.DataFrame], float], features: pd.Series
) -> float:
    X = pd.DataFrame(
        index=pd.Index([0]), columns=pd.Index(X_COLS), dtype=float
    )
    for c in X_COLS:
        val = features.get(c, 0.0)
        if c not in features.index or bool(pd.isna(val)):
            logger.warning(
                "safe_predict: feature '%s' missing — defaulting to 0.0", c
            )
            X.loc[0, c] = 0.0
        else:
            X.loc[0, c] = val
        v = X.loc[0, c]
        v_f = float(v) if isinstance(v, (int, float)) else float("nan")
        if not np.isfinite(v_f):
            logger.warning(
                "safe_predict: feature '%s' is non-finite (%s)"
                " — defaulting to 0.0",
                c,
                v,
            )
            X.loc[0, c] = 0.0
    return predict_fn(X)
