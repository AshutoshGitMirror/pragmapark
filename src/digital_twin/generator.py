import numpy as np
import logging
import random
import os
from typing import List, Tuple

logger = logging.getLogger(__name__)

SEED = int(os.getenv("PRAGMA_SEED", "42"))
random.seed(SEED)
np.random.seed(SEED)


class Generator:
    def __init__(self, latent_dim: int = 8, kl_weight: float = 0.05):
        self.latent_dim = latent_dim
        self.hidden_dim = 16
        self.kl_weight = kl_weight

        # Encoder weights
        self.W_e1 = np.random.randn(4, self.hidden_dim) * 0.1
        self.b_e1 = np.zeros(self.hidden_dim)
        self.W_mu = np.random.randn(self.hidden_dim, latent_dim) * 0.1
        self.b_mu = np.zeros(latent_dim)
        self.W_logvar = np.random.randn(self.hidden_dim, latent_dim) * 0.1
        self.b_logvar = np.zeros(latent_dim)

        # Decoder weights (corresponds to original W and b)
        self.W = np.random.randn(latent_dim, 4) * 0.1
        self.b = np.zeros(4)

        # Adam optimizer parameters
        self.m = {}
        self.v = {}
        self.t = 0

        self.trained = False

    def forward(self, latent: np.ndarray) -> np.ndarray:
        return np.tanh(latent @ self.W + self.b)

    def synthesize_scenario(self, base_occupancy: float, base_price: float) -> np.ndarray:
        z = np.random.randn(self.latent_dim)
        synthetic = self.forward(z)
        occ_delta = float(synthetic[0]) * 0.3
        price_mult = float(synthetic[1]) * 0.5
        new_occ = np.clip(base_occupancy + occ_delta, 0, 1)
        new_price = np.clip(base_price * (1 + price_mult), 5, 50)
        congestion = float(synthetic[2])
        return np.array([new_occ, new_price, congestion])

    def _adam_update(self, name: str, param: np.ndarray, grad: np.ndarray, lr: float) -> np.ndarray:
        if name not in self.m:
            self.m[name] = np.zeros_like(param)
            self.v[name] = np.zeros_like(param)
        self.m[name] = 0.9 * self.m[name] + 0.1 * grad
        self.v[name] = 0.999 * self.v[name] + 0.001 * (grad ** 2)
        m_hat = self.m[name] / (1 - 0.9 ** self.t)
        v_hat = self.v[name] / (1 - 0.999 ** self.t)
        return param - lr * m_hat / (np.sqrt(v_hat) + 1e-8)

    def train_step(self, real_samples: np.ndarray, lr: float = 0.001) -> float:
        batch_size = len(real_samples)
        if batch_size == 0:
            return 0.0

        # Ensure we have exactly 4 columns
        if real_samples.shape[1] < 4:
            padding = np.zeros((batch_size, 4 - real_samples.shape[1]))
            x = np.hstack([real_samples, padding])
        else:
            x = real_samples[:, :4]

        # 1. Forward Pass (Encoder)
        h1 = np.tanh(x @ self.W_e1 + self.b_e1)
        mu = h1 @ self.W_mu + self.b_mu
        log_var = h1 @ self.W_logvar + self.b_logvar
        log_var = np.clip(log_var, -20.0, 20.0)

        # Reparameterization Trick
        std = np.exp(0.5 * log_var)
        eps = np.random.randn(*mu.shape)
        z = mu + eps * std

        # Forward Pass (Decoder)
        fake = self.forward(z)

        # 2. Compute Loss
        recon_loss = np.mean((fake - x) ** 2)
        kl_loss = -0.5 * np.mean(1 + log_var - mu**2 - np.exp(log_var))
        loss = recon_loss + self.kl_weight * kl_loss

        # 3. Backward Pass
        # Gradient of recon_loss w.r.t fake
        d_fake = 2 * (fake - x) / (batch_size * 4)

        # Decoder activation (tanh)
        d_dec_in = d_fake * (1 - fake ** 2)

        # Decoder weights & bias
        dW = z.T @ d_dec_in
        db = np.sum(d_dec_in, axis=0)

        # Gradient w.r.t z
        dz = d_dec_in @ self.W.T

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

        # Hidden layer h1 gradient
        dh1 = d_mu @ self.W_mu.T + d_logvar @ self.W_logvar.T

        # Hidden activation (tanh)
        dh1_in = dh1 * (1 - h1 ** 2)

        # Encoder input layer
        dW_e1 = x.T @ dh1_in
        db_e1 = np.sum(dh1_in, axis=0)

        # 4. Adam Updates
        self.t += 1
        self.W_e1 = self._adam_update("W_e1", self.W_e1, dW_e1, lr)
        self.b_e1 = self._adam_update("b_e1", self.b_e1, db_e1, lr)
        self.W_mu = self._adam_update("W_mu", self.W_mu, dW_mu, lr)
        self.b_mu = self._adam_update("b_mu", self.b_mu, db_mu, lr)
        self.W_logvar = self._adam_update("W_logvar", self.W_logvar, dW_logvar, lr)
        self.b_logvar = self._adam_update("b_logvar", self.b_logvar, db_logvar, lr)
        self.W = self._adam_update("W", self.W, dW, lr)
        self.b = self._adam_update("b", self.b, db, lr)

        self.trained = True
        return float(loss)

    def train(self, real_data: np.ndarray, epochs: int = 500) -> List[float]:
        epochs = min(epochs, 1000)
        losses = []
        for ep in range(epochs):
            idx = np.random.choice(len(real_data), min(32, len(real_data)), replace=False)
            batch = real_data[idx]
            target = batch[:, :4]
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
        """Fine-tune the VAE on a real session outcome.

        Paper intent: generative model should adapt to observed parking
        dynamics so that counterfactual scenarios reflect actual conditions.

        Each session produces one 4D training vector:
          [occ_rate, price/50, congestion_val, duration_hours/24]

        Training triggers when the buffer reaches ONLINE_BATCH_SIZE.
        Returns stats about whether training occurred.
        """
        congestion_map = {"normal": 0.0, "moderate": 0.33, "high": 0.66, "critical": 1.0}
        congestion_val = congestion_map.get(congestion, 0.0)

        sample = np.array([[
            float(np.clip(occ_rate, 0, 1)),
            float(np.clip(price / 50.0, 0, 1)),
            congestion_val,
            float(np.clip(duration_hours / 24.0, 0, 1)),
        ]])

        # Append to session buffer
        if not hasattr(self, '_online_buffer'):
            self._online_buffer = []
            self._online_steps = 0
        self._online_buffer.append(sample)

        # Train when buffer is full
        batch_size = int(os.getenv("ONLINE_BATCH_SIZE", "10"))
        if len(self._online_buffer) >= batch_size:
            batch = np.vstack(self._online_buffer)
            loss = self.train_step(batch, lr=learning_rate)
            self._online_steps += 1
            self._online_buffer = []
            logger.info("generator.online_update batch=%d loss=%.6f total_steps=%d",
                        batch_size, loss, self._online_steps)
            return {"trained": True, "samples": batch_size, "loss": loss, "total_steps": self._online_steps}

        return {"trained": False, "samples": len(self._online_buffer), "loss": None, "total_steps": self._online_steps}
