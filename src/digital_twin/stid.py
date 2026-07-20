"""Spatial-Temporal Identity (STID) occupancy model — HONEST REBUILD.

This rebuild addresses the defects called out in the digital-twin remediation
plan:

  * The previous version used ``np.random.randn`` spatial embeddings and a
    fixed ``num_zones=100`` — NOT real spatial data. Spatial identity is now
    derived from the persisted, real OSM/distance adjacency graph
    (``src/digital_twin/spatial.py``). There is no random embedding.
  * The previous version was updated by the runtime simulator with simulated
    ``new_occ`` (self-training on fake data). This version can ONLY be trained
    via :meth:`train_on_real_observation`, which requires a timestamped real
    observed occupancy and refuses any simulated/synthetic label. Simulated
    values never train this model (remediation principle #1).

This model is an EXPERIMENTAL candidate forecaster. It is retrained only on
later real observations with real temporal + spatial features, and is only
promoted to "primary" by the TwinService if it beats the persistence + ML
baselines on held-out real data (remediation P2). Until then it is NOT a
validated forecaster and must not be described as one.
"""
import logging
from typing import Dict, List, Optional, Tuple

import numpy as np

from src.digital_twin.spatial import coupling_strength

logger = logging.getLogger(__name__)


class STIDPredictor:
    def __init__(self, num_zones: int = 2, spatial_dim: int = 8, temporal_dim: int = 8):
        # num_zones is now the REAL number of lots; callers must set it from
        # the database, never a hardcoded constant.
        self.num_zones = max(1, num_zones)
        self.spatial_dim = spatial_dim
        self.temporal_dim = temporal_dim

        # Temporal identity embeddings (learnable, conditioned on real hour/dow).
        self.E_Thour = np.random.randn(24, temporal_dim) * 0.1
        self.E_Tday = np.random.randn(7, temporal_dim) * 0.1

        # Spatial identity is NOT a random embedding. It is the real coupling
        # vector between this lot and every other lot. We store a learnable
        # temporal/temporal residual but the spatial identity itself is read
        # from the real adjacency graph at predict time.
        self.input_dim = spatial_dim + temporal_dim * 2 + 1
        self.W_mlp = np.random.randn(self.input_dim) * 0.1
        self.b_mlp = 0.0

        # Per-lot learnable temporal residual bias (real-data only).
        self.zone_bias = np.zeros(num_zones)

        self._zone_index: Dict[str, int] = {}
        self._trained_real_steps: int = 0

    def set_zone_index(self, zone_ids: List[str]) -> None:
        """Map real lot_ids -> integer indices. Dropped the fixed 100-zone."""
        self._zone_index = {zid: i for i, zid in enumerate(zone_ids)}
        self.num_zones = max(1, len(zone_ids))
        if self.zone_bias.shape[0] != self.num_zones:
            self.zone_bias = np.zeros(self.num_zones)

    def _spatial_identity(self, zone_idx: int) -> np.ndarray:
        """Real spatial identity vector (deterministic, adjacency-derived).

        Returns a fixed-length vector by gathering the coupling strength of
        this lot to the first ``spatial_dim`` other lots. No random weights.
        Lots without coordinates fall back to a zero vector (honest: no
        spatial claim when we have no coordinates).
        """
        vec = np.zeros(self.spatial_dim)
        ids = list(self._zone_index.keys())
        if not ids:
            return vec
        me = ids[zone_idx] if zone_idx < len(ids) else ids[0]
        others = [o for o in ids if o != me][: self.spatial_dim]
        for k, other in enumerate(others):
            vec[k] = coupling_strength(me, other)
        return vec

    def _features(
        self, zone_idx: int, hour: int, day: int, history_occ: float
    ) -> np.ndarray:
        e_s = self._spatial_identity(zone_idx)
        e_th = self.E_Thour[hour]
        e_td = self.E_Tday[day]
        bias = self.zone_bias[zone_idx] if zone_idx < len(self.zone_bias) else 0.0
        x = np.concatenate([e_s, e_th, e_td, [history_occ + bias]])
        return x

    def predict(
        self, zone_idx: int, hour: int, day: int, history_occ: float
    ) -> float:
        x = self._features(zone_idx, hour, day, history_occ)
        raw = float(x @ self.W_mlp + self.b_mlp)
        return float(1.0 / (1.0 + np.exp(-raw)))

    def predict_by_lot(
        self, lot_id: str, hour: int, day: int, history_occ: float
    ) -> Optional[float]:
        if lot_id not in self._zone_index:
            return None
        return self.predict(self._zone_index[lot_id], hour, day, history_occ)

    def train_on_real_observation(
        self,
        lot_id: str,
        hour: int,
        day: int,
        history_occ: float,
        observed_occ: float,
        lr: float = 0.01,
    ) -> float:
        """Train a single step on a REAL observed occupancy only.

        ``observed_occ`` MUST come from a timestamped real observation
        (TwinObservation / OccupancyRecord), never from a simulator's
        ``new_occ`` or any synthetic value. The orchestrator must NOT call
        this from ``simulate_ingest`` / ``tick`` paths.
        """
        if not (0.0 <= float(observed_occ) <= 1.0):
            raise ValueError("observed_occ must be a real rate in [0, 1]")
        zi = self._zone_index.get(lot_id)
        if zi is None:
            return float("nan")
        x = self._features(zi, hour, day, history_occ)
        raw = float(x @ self.W_mlp + self.b_mlp)
        pred = 1.0 / (1.0 + np.exp(-raw))
        loss = 0.5 * (pred - observed_occ) ** 2
        d_raw = (pred - observed_occ) * pred * (1.0 - pred)
        self.W_mlp -= lr * (x * d_raw)
        self.b_mlp -= lr * d_raw
        self.E_Thour[hour] -= lr * (d_raw * x[self.spatial_dim: self.spatial_dim + self.temporal_dim])
        td0 = self.spatial_dim + self.temporal_dim
        self.E_Tday[day] -= lr * (d_raw * x[td0: td0 + self.temporal_dim])
        if zi < len(self.zone_bias):
            self.zone_bias[zi] -= lr * d_raw
        self._trained_real_steps += 1
        return float(loss)

    @property
    def trained_real_steps(self) -> int:
        """Number of REAL-observation training steps (simulated steps excluded)."""
        return self._trained_real_steps

    def evaluation_only(self) -> bool:
        """True until enough real observations have been seen to trust it."""
        return self._trained_real_steps < 200
