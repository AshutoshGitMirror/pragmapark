import pandas as pd
import numpy as np
from src.features.builder import (
    safe_predict,
    build_features_from_records,
    X_COLS,
)


def _dummy_predict(df: pd.DataFrame) -> float:
    return 0.65


class TestFeaturesBuilder:
    def test_x_cols_defined(self):
        assert len(X_COLS) >= 18
        assert "occupied_slots" in X_COLS

    def test_build_features_from_records_none_when_empty(self):
        result = build_features_from_records([], 100)
        assert result is None

    def test_build_features_from_records_none_when_one(self):
        result = build_features_from_records(
            [{"occupancy_rate": 0.5, "timestamp": "2025-01-01T12:00:00"}], 100
        )
        assert result is None

    def test_build_features_from_records_two(self):
        records = [
            {
                "occupancy_rate": 0.4,
                "occupied_slots": 40,
                "timestamp": "2025-01-01T12:00:00",
            },
            {
                "occupancy_rate": 0.5,
                "occupied_slots": 50,
                "timestamp": "2025-01-01T12:15:00",
            },
        ]
        result = build_features_from_records(records, 100)
        assert result is not None
        assert "occupancy_rate" in result
        assert result["occupied_slots"] == 50

    def test_safe_predict_returns_float(self):
        features = pd.Series({"occupancy_rate": 0.5, "occ_lag_15m": 0.4})
        result = safe_predict(_dummy_predict, features)
        assert result == 0.65

    def test_safe_predict_adds_missing_cols(self):
        features = pd.Series({"occupancy_rate": 0.5})
        result = safe_predict(_dummy_predict, features)
        assert result == 0.65

    def test_safe_predict_handles_nan(self):
        features = pd.Series({"occupancy_rate": 0.5, "occ_lag_15m": np.nan})
        result = safe_predict(_dummy_predict, features)
        assert result == 0.65

    def test_safe_predict_corrects_inf(self):
        features = pd.Series({"occupancy_rate": 0.5, "occ_lag_15m": np.inf})
        result = safe_predict(_dummy_predict, features)
        assert result == 0.65
