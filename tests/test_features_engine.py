import os
import tempfile
import pandas as pd
from src.features.engine import (
    process_raw_to_features,
    build_features_from_records,
)


def _make_csv(tmpdir, lines: list[str]) -> str:
    path = os.path.join(tmpdir, "test.csv")
    with open(path, "w") as f:
        for line in lines:
            f.write(line + "\n")
    return path


class TestProcessRawToFeatures:
    def test_basic_csv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _make_csv(
                tmpdir,
                [
                    "SystemCodeNumber,Capacity,Occupancy,LastUpdated",
                    "LOT_1,100,45,2025-01-01 12:00:00",
                    "LOT_1,100,46,2025-01-01 12:15:00",
                    "LOT_1,100,47,2025-01-01 12:30:00",
                    "LOT_1,100,48,2025-01-01 12:45:00",
                    "LOT_1,100,49,2025-01-01 13:00:00",
                    "LOT_1,100,50,2025-01-01 13:15:00",
                    "LOT_1,100,51,2025-01-01 13:30:00",
                    "LOT_1,100,52,2025-01-01 13:45:00",
                ],
            )
            result = process_raw_to_features(path)
            assert len(result) >= 1
            assert "lot_id" in result.columns
            assert "occupancy_rate" in result.columns
            assert result["lot_id"].iloc[0] == "LOT_1"

    def test_raises_on_too_few_columns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _make_csv(
                tmpdir,
                [
                    "a,b,c",
                    "LOT_1,100,45",
                ],
            )
            try:
                process_raw_to_features(path)
                assert False, "should raise"
            except ValueError:
                pass

    def test_handles_zero_capacity(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _make_csv(
                tmpdir,
                [
                    "SystemCodeNumber,Capacity,Occupancy,LastUpdated",
                    "LOT_1,0,0,2025-01-01 12:00:00",
                    "LOT_1,0,5,2025-01-01 12:15:00",
                    "LOT_1,0,10,2025-01-01 12:30:00",
                    "LOT_1,0,15,2025-01-01 12:45:00",
                    "LOT_1,0,20,2025-01-01 13:00:00",
                    "LOT_1,0,25,2025-01-01 13:15:00",
                    "LOT_1,0,30,2025-01-01 13:30:00",
                    "LOT_1,0,35,2025-01-01 13:45:00",
                ],
            )
            result = process_raw_to_features(path)
            assert result["total_slots"].iloc[0] == 500

    def test_multiple_lots(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _make_csv(
                tmpdir,
                [
                    "SystemCodeNumber,Capacity,Occupancy,LastUpdated",
                    "LOT_1,100,45,2025-01-01 12:00:00",
                    "LOT_1,100,46,2025-01-01 12:15:00",
                    "LOT_1,100,47,2025-01-01 12:30:00",
                    "LOT_1,100,48,2025-01-01 12:45:00",
                    "LOT_1,100,49,2025-01-01 13:00:00",
                    "LOT_1,100,50,2025-01-01 13:15:00",
                    "LOT_1,100,51,2025-01-01 13:30:00",
                    "LOT_1,100,52,2025-01-01 13:45:00",
                    "LOT_2,200,80,2025-01-01 12:00:00",
                    "LOT_2,200,82,2025-01-01 12:15:00",
                    "LOT_2,200,84,2025-01-01 12:30:00",
                    "LOT_2,200,86,2025-01-01 12:45:00",
                    "LOT_2,200,88,2025-01-01 13:00:00",
                    "LOT_2,200,90,2025-01-01 13:15:00",
                    "LOT_2,200,92,2025-01-01 13:30:00",
                    "LOT_2,200,94,2025-01-01 13:45:00",
                ],
            )
            result = process_raw_to_features(path)
            lots = result["lot_id"].unique()
            assert len(lots) == 2

    def test_feature_columns_present(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _make_csv(
                tmpdir,
                [
                    "SystemCodeNumber,Capacity,Occupancy,LastUpdated",
                    "LOT_1,100,45,2025-01-01 12:00:00",
                    "LOT_1,100,46,2025-01-01 12:15:00",
                    "LOT_1,100,47,2025-01-01 12:30:00",
                    "LOT_1,100,48,2025-01-01 12:45:00",
                    "LOT_1,100,49,2025-01-01 13:00:00",
                    "LOT_1,100,50,2025-01-01 13:15:00",
                    "LOT_1,100,51,2025-01-01 13:30:00",
                    "LOT_1,100,52,2025-01-01 13:45:00",
                ],
            )
            result = process_raw_to_features(path)
            for col in [
                "hour_sin",
                "hour_cos",
                "occ_lag_15m",
                "pe_net_flux",
                "is_weekend",
            ]:
                assert col in result.columns, f"Missing column: {col}"


class TestBuildFeaturesFromRecords:
    def test_none_when_empty(self):
        assert build_features_from_records([], 100) is None

    def test_none_when_one(self):
        records = [
            {
                "occupancy_rate": 0.5,
                "timestamp": pd.Timestamp("2025-01-01 12:00"),
            }
        ]
        assert build_features_from_records(records, 100) is None

    def test_returns_series_with_two(self):
        records = [
            {
                "occupancy_rate": 0.4,
                "occupied_slots": 40,
                "timestamp": pd.Timestamp("2025-01-01 12:00"),
            },
            {
                "occupancy_rate": 0.5,
                "occupied_slots": 50,
                "timestamp": pd.Timestamp("2025-01-01 12:15"),
            },
        ]
        result = build_features_from_records(records, 100)
        assert result is not None
        assert result["occupancy_rate"] == 0.5
        assert "occ_lag_15m" in result

    def test_handles_records_without_occupancy_rate(self):
        records = [
            {
                "occupied_slots": 40,
                "timestamp": pd.Timestamp("2025-01-01 12:00"),
            },
            {
                "occupied_slots": 50,
                "timestamp": pd.Timestamp("2025-01-01 12:15"),
            },
        ]
        result = build_features_from_records(records, 100)
        assert result is not None
        assert result["occupied_slots"] == 50

    def test_includes_time_features(self):
        records = [
            {
                "occupancy_rate": 0.4,
                "occupied_slots": 40,
                "timestamp": pd.Timestamp("2025-01-01 12:00"),
            },
            {
                "occupancy_rate": 0.5,
                "occupied_slots": 50,
                "timestamp": pd.Timestamp("2025-01-01 12:15"),
            },
        ]
        result = build_features_from_records(records, 100)
        assert result is not None
        assert "hour_sin" in result.index
        assert "dow_sin" in result.index
