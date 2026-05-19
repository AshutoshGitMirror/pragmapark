import pandas as pd
import numpy as np

X_COLS = [
    'occupied_slots', 'total_slots', 'occ_lag_15m', 'occ_lag_1h', 'net_flux',
    'pe_arrival_rate', 'pe_departure_rate', 'pe_turnover', 'pe_anomaly', 'pe_change_point',
    'hour_sin', 'hour_cos', 'hour_sq',
    'dow_sin', 'dow_cos', 'is_weekend',
    'occ_roll_mean_3h', 'occ_roll_std_3h', 'occ_acceleration',
]


def safe_predict(model_fn, features: pd.Series):
    if features is None:
        return 0.5
    try:
        X = pd.DataFrame(index=[0], columns=X_COLS, dtype=float)
        for c in X_COLS:
            X[c] = float(features.get(c, 0.0))
        return float(model_fn(X))
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"safe_predict error: {e}")
        return 0.5


def build_features_from_records(records: list, cols: list = None) -> pd.Series:
    if not records or len(records) < 2:
        return None
    if cols is None:
        cols = X_COLS
    data = {c: 0.0 for c in cols}
    for r in records:
        if hasattr(r, '__dict__'):
            r = r.__dict__
        for k in cols:
            val = r.get(k, 0.0)
            try:
                data[k] = float(val)
            except (ValueError, TypeError):
                data[k] = 0.0
    return pd.Series(data)
