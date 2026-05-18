import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ParkingEvent:
    lot_id: str
    timestamp: float
    event_type: str
    slot_index: int
    occupancy_before: float
    occupancy_after: float


class ParkingEventExtractor:
    def __init__(self, window_minutes: int = 15):
        self.window_minutes = window_minutes

    def extract_events(self, df: pd.DataFrame, occupancy_col: str = "occupancy_rate") -> pd.DataFrame:
        result = df.copy()
        g = result.groupby("lot_id", group_keys=False)
        result["pe_arrival_rate"] = g[occupancy_col].transform(
            lambda s: s.diff().clip(lower=0).rolling(4, min_periods=1).mean()
        )
        result["pe_departure_rate"] = g[occupancy_col].transform(
            lambda s: (-s.diff()).clip(lower=0).rolling(4, min_periods=1).mean()
        )
        result["pe_net_flux"] = g[occupancy_col].transform(lambda s: s.diff().fillna(0))
        result["pe_turnover"] = g[occupancy_col].transform(
            lambda s: s.diff().abs().rolling(8, min_periods=1).sum()
        )
        mean_occ = g[occupancy_col].transform("mean").shift(1)
        std_occ = g[occupancy_col].transform("std").shift(1)
        result["pe_anomaly"] = ((result[occupancy_col] - mean_occ).abs() > 2 * std_occ).astype(float)
        result["pe_anomaly"] = result["pe_anomaly"].fillna(0)
        result["pe_change_point"] = self._detect_change_points(df, occupancy_col)
        return result

    def _detect_change_points(self, df: pd.DataFrame, occ_col: str) -> pd.Series:
        g = df.groupby("lot_id")[occ_col]
        cusum = g.transform(lambda s: (s - s.rolling(8, min_periods=1).mean()).fillna(0))
        threshold = cusum.rolling(4, min_periods=1).std().fillna(0) * 1.5
        return (cusum.abs() > threshold).astype(float)

    def get_event_summary(self, df_with_pe: pd.DataFrame) -> dict:
        return {
            "total_rows": len(df_with_pe),
            "mean_arrival_rate": float(df_with_pe["pe_arrival_rate"].mean()),
            "mean_departure_rate": float(df_with_pe["pe_departure_rate"].mean()),
            "mean_turnover": float(df_with_pe["pe_turnover"].mean()),
            "anomaly_pct": float(df_with_pe["pe_anomaly"].mean() * 100),
            "change_point_pct": float(df_with_pe["pe_change_point"].mean() * 100),
            "net_flux_std": float(df_with_pe["pe_net_flux"].std()),
        }
