import numpy as np
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


class STIDPredictor:
    """Spatial-Temporal Identity (STID) network for occupancy forecasting.

    Paper alignment (Piccialli et al. 2025):
    - Encodes spatial identity (where the parking zone is relative to others)
    - Encodes temporal identity (hour-of-day, day-of-week context)
    - Integrates neighboring zone influence (spatial correlation)
    - Fully NumPy-based network with forward/backward passes.
    """

    def __init__(
        self, num_zones: int = 4, spatial_dim: int = 8, temporal_dim: int = 8
    ):
        self.num_zones = num_zones
        self.spatial_dim = spatial_dim
        self.temporal_dim = temporal_dim

        # 1. Spatial Identity Embeddings (learnable node identity)
        self.E_S = np.random.randn(num_zones, spatial_dim) * 0.1

        # 2. Temporal Identity Embeddings (learnable time-of-day & day-of-week
        # identity)
        self.E_Thour = np.random.randn(24, temporal_dim) * 0.1
        self.E_Tday = np.random.randn(7, temporal_dim) * 0.1

        # 3. Spatial correlation matrix (neighbor influence, learnable)
        self.W_spatial = np.random.randn(num_zones, num_zones) * 0.1

        # 4. Regression weights for final prediction
        # Feature size: spatial_dim (target) + spatial_dim (neighbors) + 2 *
        # temporal_dim + 1 (history)
        self.input_dim = spatial_dim * 2 + temporal_dim * 2 + 1
        self.W_mlp = np.random.randn(self.input_dim) * 0.1
        self.b_mlp = 0.0

    def _get_features(
        self, zone_idx: int, hour: int, day: int, history_occ: float
    ) -> Tuple[np.ndarray, np.ndarray]:
        # Spatial identity of target
        e_s = self.E_S[zone_idx]  # (spatial_dim,)

        # Neighbor spatial influence weighted by self.W_spatial
        spatial_weights = self.W_spatial[zone_idx]  # (num_zones,)
        e_s_neighbors = spatial_weights @ self.E_S  # (spatial_dim,)

        # Temporal identities
        e_th = self.E_Thour[hour]  # (temporal_dim,)
        e_td = self.E_Tday[day]  # (temporal_dim,)

        # Fused vector: concatenate target spatial, neighbor spatial, temporal
        # hour, temporal day, and base history
        x = np.concatenate(
            [e_s, e_s_neighbors, e_th, e_td, [history_occ]]
        )  # (input_dim,)

        return x, e_s_neighbors

    def predict(
        self, zone_idx: int, hour: int, day: int, history_occ: float
    ) -> float:
        """Predict the occupancy rate for the zone."""
        x, _ = self._get_features(zone_idx, hour, day, history_occ)
        pred = float(x @ self.W_mlp + self.b_mlp)
        # Sigmoid to keep output in [0, 1]
        pred = 1.0 / (1.0 + np.exp(-pred))
        return pred

    def train_step(
        self,
        zone_idx: int,
        hour: int,
        day: int,
        history_occ: float,
        target: float,
        lr: float = 0.01,
    ) -> float:
        """Execute a single train step using gradient descent."""
        e_s = self.E_S[zone_idx]
        spatial_weights = self.W_spatial[zone_idx]
        e_s_neighbors = spatial_weights @ self.E_S
        e_th = self.E_Thour[hour]
        e_td = self.E_Tday[day]

        x = np.concatenate([e_s, e_s_neighbors, e_th, e_td, [history_occ]])

        raw_pred = float(x @ self.W_mlp + self.b_mlp)
        pred = 1.0 / (1.0 + np.exp(-raw_pred))

        # MSE Loss
        loss = 0.5 * (pred - target) ** 2

        # Gradients
        d_pred = pred - target
        d_raw = d_pred * pred * (1.0 - pred)  # Sigmoid derivative

        # Gradient w.r.t MLP weights
        dW_mlp = x * d_raw
        db_mlp = d_raw

        # Gradient w.r.t input features
        dx = self.W_mlp * d_raw

        # Split dx into components
        de_s = dx[0: self.spatial_dim]
        de_s_neighbors = dx[self.spatial_dim: 2 * self.spatial_dim]
        de_th = dx[
            2 * self.spatial_dim: 2 * self.spatial_dim + self.temporal_dim
        ]
        de_td = dx[
            2 * self.spatial_dim + self.temporal_dim: 2 * self.spatial_dim
            + 2 * self.temporal_dim
        ]

        # Gradient w.r.t W_spatial
        dw_spatial = self.E_S @ de_s_neighbors

        # Gradient w.r.t E_S (direct target + neighbor propagation)
        dE_S = np.zeros_like(self.E_S)
        dE_S[zone_idx] += de_s
        for i in range(self.num_zones):
            dE_S[i] += de_s_neighbors * spatial_weights[i]

        # Update weights
        self.W_mlp -= lr * dW_mlp
        self.b_mlp -= lr * db_mlp
        self.E_S -= lr * dE_S
        self.W_spatial[zone_idx] -= lr * dw_spatial
        self.E_Thour[hour] -= lr * de_th
        self.E_Tday[day] -= lr * de_td

        return loss
