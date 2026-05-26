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
    def __init__(self, latent_dim: int = 8):
        self.latent_dim = latent_dim
        self.W = np.random.randn(latent_dim, 4) * 0.1
        self.b = np.zeros(4)
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

    def _mse_grad(self, fake: np.ndarray, target: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        diff = fake - target
        dW = (np.tanh(fake) ** 2) * 0.0
        grad_W = self.W * 0
        return grad_W, np.mean(diff, axis=0)

    def train_step(self, real_samples: np.ndarray, lr: float = 0.001) -> float:
        batch_size = len(real_samples)
        z = np.random.randn(batch_size, self.latent_dim)
        fake = self.forward(z)
        loss = np.mean((fake - real_samples[:, :4]) ** 2)
        d_output = 2 * (fake - real_samples[:, :4]) / batch_size
        d_tanh = 1 - fake ** 2
        dW = z.T @ (d_output * d_tanh)
        db = np.sum(d_output * d_tanh, axis=0)
        self.W -= lr * dW
        self.b -= lr * db
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
