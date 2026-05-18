import numpy as np
from typing import List, Tuple


class GenerativeSimulator:
    def __init__(self, latent_dim: int = 8):
        self.latent_dim = latent_dim
        self.generator_W = np.random.randn(latent_dim, 4) * 0.1
        self.generator_b = np.zeros(4)
        self.critic_W = np.random.randn(4, 1) * 0.1
        self.critic_b = np.zeros(1)
        self.trained = False

    def generate(self, latent: np.ndarray) -> np.ndarray:
        hidden = np.tanh(latent @ self.generator_W + self.generator_b)
        return hidden

    def synthesize_scenario(self, base_occupancy: float, base_price: float) -> np.ndarray:
        z = np.random.randn(self.latent_dim)
        synthetic = self.generate(z)
        occ_delta = float(synthetic[0]) * 0.3
        price_mult = float(synthetic[1]) * 0.5
        new_occ = np.clip(base_occupancy + occ_delta, 0, 1)
        new_price = np.clip(base_price * (1 + price_mult), 5, 50)
        congestion = float(synthetic[2])
        return np.array([new_occ, new_price, congestion])

    def train_step(self, real_samples: np.ndarray, lr: float = 0.001) -> Tuple[float, float]:
        batch_size = len(real_samples)
        z = np.random.randn(batch_size, self.latent_dim)
        fake = self.generate(z)

        real_score = real_samples @ self.critic_W + self.critic_b
        fake_score = fake @ self.critic_W + self.critic_b
        critic_loss = float(np.mean(fake_score - real_score))

        grad_critic = np.mean(fake - real_samples, axis=0, keepdims=True).T
        self.critic_W += lr * grad_critic
        self.critic_b += lr * np.mean(fake_score - real_score, axis=0, keepdims=False)

        z2 = np.random.randn(batch_size, self.latent_dim)
        fake2 = self.generate(z2)
        fake_score2 = fake2 @ self.critic_W + self.critic_b
        gen_loss = -float(np.mean(fake_score2))

        grad_gen = z2.T @ (np.ones((batch_size, 1)) @ self.critic_W.T * (1 - fake2 ** 2))
        self.generator_W += lr * grad_gen / batch_size
        self.generator_b += lr * np.mean(-self.critic_W.T * (1 - fake2 ** 2), axis=0)

        self.trained = True
        return critic_loss, gen_loss

    def train(self, real_data: np.ndarray, epochs: int = 500) -> List[Tuple[float, float]]:
        losses = []
        for ep in range(epochs):
            idx = np.random.choice(len(real_data), min(32, len(real_data)), replace=False)
            batch = real_data[idx]
            c_loss, g_loss = self.train_step(batch)
            if (ep + 1) % 100 == 0:
                losses.append((c_loss, g_loss))
        self.trained = True
        print(f"  Generative Model trained: {epochs} steps")
        return losses
