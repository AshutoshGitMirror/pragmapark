import numpy as np
import logging
import random
import os
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)

SEED = int(os.getenv("PRAGMA_SEED", "42"))
random.seed(SEED)
np.random.seed(SEED)

SCENARIO_NAMES = [
    "zone_closure", "price_surge", "capacity_expansion",
    "weather_disruption", "holiday_spike",
]


class Generator:
    """Conditional VAE (CVAE) for parking scenario generation.

    Paper: CVAE-WGAN hybrid where the CVAE learns the conditional distribution
    of parking states P(state | scenario_type). The scenario type is a one-hot
    condition concatenated to both encoder input and decoder latent, enabling
    purely generative counterfactual scenarios without hardcoded multipliers.

    Architecture:
        Encoder:  [state(4) + cond(N)] → hidden(16) → mu(8) + logvar(8)
        Decoder:  [latent(8) + cond(N)] → output(4)  (tanh activation)
    """

    def __init__(self, latent_dim: int = 8, kl_weight: float = 0.05,
                 num_scenarios: int = 5):
        self.latent_dim = latent_dim
        self.hidden_dim = 16
        self.kl_weight = kl_weight
        self.num_scenarios = num_scenarios
        self.state_dim = 4
        self.cond_dim = num_scenarios
        self.input_dim = self.state_dim + self.cond_dim
        self.decoder_input_dim = latent_dim + self.cond_dim

        # Encoder weights: input (state + one-hot condition) -> hidden
        self.W_e1 = np.random.randn(self.input_dim, self.hidden_dim) * 0.1
        self.b_e1 = np.zeros(self.hidden_dim)
        self.W_mu = np.random.randn(self.hidden_dim, latent_dim) * 0.1
        self.b_mu = np.zeros(latent_dim)
        self.W_logvar = np.random.randn(self.hidden_dim, latent_dim) * 0.1
        self.b_logvar = np.zeros(latent_dim)

        # Decoder weights: latent + one-hot condition -> output
        self.W = np.random.randn(self.decoder_input_dim, self.state_dim) * 0.1
        self.b = np.zeros(self.state_dim)

        # Adam optimizer parameters
        self.m = {}
        self.v = {}
        self.t = 0

        self.trained = False

    def _make_condition(self, scenario_idx: int) -> np.ndarray:
        """Create one-hot condition vector for a scenario index."""
        c = np.zeros(self.num_scenarios)
        c[scenario_idx % self.num_scenarios] = 1.0
        return c

    def _make_condition_batch(self, indices: np.ndarray) -> np.ndarray:
        """Create batch of one-hot condition vectors."""
        batch = np.zeros((len(indices), self.num_scenarios))
        batch[np.arange(len(indices)), indices % self.num_scenarios] = 1.0
        return batch

    def forward(self, latent: np.ndarray, condition: np.ndarray) -> np.ndarray:
        """Decoder forward pass: concat(latent, condition) -> output."""
        zc = np.concatenate([latent, condition], axis=-1)
        return np.tanh(zc @ self.W + self.b)

    def synthesize_scenario(self, base_occupancy: float, base_price: float,
                            scenario_idx: Optional[int] = None) -> np.ndarray:
        """Generate a scenario-conditional state from the CVAE.

        When scenario_idx is None (backward compat), samples a random scenario.
        Returns [occupancy_rate, price, congestion, 0] vector.
        """
        if scenario_idx is None:
            scenario_idx = np.random.randint(self.num_scenarios)
        cond = self._make_condition(scenario_idx)
        z = np.random.randn(1, self.latent_dim)  # batch dimension
        synthetic = self.forward(z, cond.reshape(1, -1)).flatten()

        occ_delta = float(synthetic[0]) * 0.3
        price_mult = float(synthetic[1]) * 0.5
        new_occ = np.clip(base_occupancy + occ_delta, 0, 1)
        new_price = np.clip(base_price * (1 + price_mult), 5, 50)
        congestion = float(synthetic[2])
        return np.array([new_occ, new_price, congestion])

    def _adam_update(self, name: str, param: np.ndarray,
                     grad: np.ndarray, lr: float) -> np.ndarray:
        if name not in self.m:
            self.m[name] = np.zeros_like(param)
            self.v[name] = np.zeros_like(param)
        self.m[name] = 0.9 * self.m[name] + 0.1 * grad
        self.v[name] = 0.999 * self.v[name] + 0.001 * (grad ** 2)
        m_hat = self.m[name] / (1 - 0.9 ** self.t)
        v_hat = self.v[name] / (1 - 0.999 ** self.t)
        return param - lr * m_hat / (np.sqrt(v_hat) + 1e-8)

    def train_step(self, real_samples: np.ndarray, lr: float = 0.001,
                   conditions: Optional[np.ndarray] = None) -> float:
        """Single training step with optional condition vectors.

        Args:
            real_samples: (batch, 4) state vectors [occ, price/50, congestion, duration/24]
            conditions: (batch, num_scenarios) one-hot condition vectors.
                        If None, random conditions are assigned.
        """
        batch_size = len(real_samples)
        if batch_size == 0:
            return 0.0

        # Ensure 4 columns
        if real_samples.shape[1] < self.state_dim:
            padding = np.zeros((batch_size, self.state_dim - real_samples.shape[1]))
            x = np.hstack([real_samples, padding])
        else:
            x = real_samples[:, :self.state_dim]

        # Assign random conditions if none provided
        if conditions is None:
            cond_indices = np.random.randint(0, self.num_scenarios, size=batch_size)
            conditions = self._make_condition_batch(cond_indices)

        # Concatenate condition to input for encoder
        x_cond = np.concatenate([x, conditions], axis=1)

        # 1. Forward Pass (Encoder)
        h1 = np.tanh(x_cond @ self.W_e1 + self.b_e1)
        mu = h1 @ self.W_mu + self.b_mu
        log_var = h1 @ self.W_logvar + self.b_logvar
        log_var = np.clip(log_var, -20.0, 20.0)

        # Reparameterization
        std = np.exp(0.5 * log_var)
        eps = np.random.randn(*mu.shape)
        z = mu + eps * std

        # Forward Pass (Decoder) — concat condition to latent
        z_cond = np.concatenate([z, conditions], axis=1)
        fake = np.tanh(z_cond @ self.W + self.b)

        # 2. Compute Loss
        recon_loss = np.mean((fake - x) ** 2)
        kl_loss = -0.5 * np.mean(1 + log_var - mu**2 - np.exp(log_var))
        loss = recon_loss + self.kl_weight * kl_loss

        # 3. Backward Pass
        d_fake = 2 * (fake - x) / (batch_size * self.state_dim)
        d_dec_in = d_fake * (1 - fake ** 2)

        # Decoder weights
        dW_z = z_cond.T @ d_dec_in
        db = np.sum(d_dec_in, axis=0)

        # Gradient w.r.t z (first latent_dim columns of z_cond)
        d_z_cond = d_dec_in @ self.W.T
        dz = d_z_cond[:, :self.latent_dim]

        # Gradient of loss w.r.t mu and log_var
        d_mu = dz + (self.kl_weight * mu) / (batch_size * self.latent_dim)

        d_logvar_recon = dz * (0.5 * eps * std)
        d_logvar_kl = (self.kl_weight * (np.exp(log_var) - 1)) / (2 * batch_size * self.latent_dim)
        d_logvar = d_logvar_recon + d_logvar_kl

        # Encoder output layers
        dW_mu = h1.T @ d_mu
        db_mu = np.sum(d_mu, axis=0)
        dW_logvar = h1.T @ d_logvar
        db_logvar = np.sum(d_logvar, axis=0)

        # Hidden layer
        dh1 = d_mu @ self.W_mu.T + d_logvar @ self.W_logvar.T
        dh1_in = dh1 * (1 - h1 ** 2)
        dW_e1 = x_cond.T @ dh1_in
        db_e1 = np.sum(dh1_in, axis=0)

        # 4. Adam Updates
        self.t += 1
        self.W_e1 = self._adam_update("W_e1", self.W_e1, dW_e1, lr)
        self.b_e1 = self._adam_update("b_e1", self.b_e1, db_e1, lr)
        self.W_mu = self._adam_update("W_mu", self.W_mu, dW_mu, lr)
        self.b_mu = self._adam_update("b_mu", self.b_mu, db_mu, lr)
        self.W_logvar = self._adam_update("W_logvar", self.W_logvar, dW_logvar, lr)
        self.b_logvar = self._adam_update("b_logvar", self.b_logvar, db_logvar, lr)
        self.W = self._adam_update("W", self.W, dW_z, lr)
        self.b = self._adam_update("b", self.b, db, lr)

        self.trained = True
        return float(loss)

    def train(self, real_data: np.ndarray, epochs: int = 500) -> List[float]:
        epochs = min(epochs, 1000)
        losses = []
        for ep in range(epochs):
            idx = np.random.choice(len(real_data), min(32, len(real_data)), replace=False)
            batch = real_data[idx]
            target = batch[:, :self.state_dim]
            loss = self.train_step(target)
            if (ep + 1) % 100 == 0:
                losses.append(loss)
                logger.info("Generator epoch %d/%d: loss=%.4f", ep + 1, epochs, loss)
        self.trained = True
        logger.info("Generator trained: %d steps", epochs)
        return losses

    def online_update(self, occ_rate: float, price: float,
                      duration_hours: float, congestion: str = "normal",
                      learning_rate: float = 0.0005) -> dict:
        """Fine-tune the CVAE on a real session outcome.

        Each session produces one 4D training vector:
          [occ_rate, price/50, congestion_val, duration_hours/24]

        Training triggers when the buffer reaches ONLINE_BATCH_SIZE.
        Real sessions use a null condition (all zeros) since they are
        not assigned to a specific scenario — the CVAE learns the marginal
        distribution P(state) alongside the conditional P(state|scenario).
        """
        congestion_map = {"normal": 0.0, "moderate": 0.33, "high": 0.66, "critical": 1.0}
        congestion_val = congestion_map.get(congestion, 0.0)

        sample = np.array([[
            float(np.clip(occ_rate, 0, 1)),
            float(np.clip(price / 50.0, 0, 1)),
            congestion_val,
            float(np.clip(duration_hours / 24.0, 0, 1)),
        ]])

        if not hasattr(self, '_online_buffer'):
            self._online_buffer = []
            self._online_steps = 0
        self._online_buffer.append(sample)

        batch_size = int(os.getenv("ONLINE_BATCH_SIZE", "10"))
        if len(self._online_buffer) >= batch_size:
            batch = np.vstack(self._online_buffer)
            # Real sessions get a null condition (marginal training)
            null_cond = np.zeros((batch_size, self.num_scenarios))
            loss = self.train_step(batch, lr=learning_rate, conditions=null_cond)
            self._online_steps += 1
            self._online_buffer = []
            logger.info("generator.online_update batch=%d loss=%.6f total_steps=%d",
                        batch_size, loss, self._online_steps)
            return {"trained": True, "samples": batch_size, "loss": loss, "total_steps": self._online_steps}

        return {"trained": False, "samples": len(self._online_buffer), "loss": None, "total_steps": self._online_steps}
