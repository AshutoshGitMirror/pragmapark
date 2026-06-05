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
    """Conditional VAE-WGAN (CVAE-WGAN) for parking scenario generation.

    Paper: CVAE-WGAN hybrid where the CVAE learns the conditional distribution
    of parking states P(state | scenario_type). A Wasserstein GAN with gradient
    penalty (WGAN-GP) provides adversarial fine-tuning so generated scenarios
    are indistinguishable from real parking dynamics.

    Architecture:
        Encoder:     [state(4) + cond(N)] → hidden(16) → mu(8) + logvar(8)
        Decoder:     [latent(8) + cond(N)] → output(4)  (tanh)
        Critic:      [state(4) + cond(N)] → hidden(16) → hidden(8) → score(1)
    """

    def __init__(self, latent_dim: int = 8, kl_weight: float = 0.05,
                 num_scenarios: int = 5, lambda_gp: float = 10.0,
                 n_critic: int = 3):
        self.latent_dim = latent_dim
        self.hidden_dim = 16
        self.kl_weight = kl_weight
        self.num_scenarios = num_scenarios
        self.state_dim = 4
        self.cond_dim = num_scenarios
        self.input_dim = self.state_dim + self.cond_dim
        self.decoder_input_dim = latent_dim + self.cond_dim
        self.lambda_gp = lambda_gp
        self.n_critic = n_critic

        # === CVAE weights ===
        # Encoder: [state + cond] -> hidden -> mu + logvar
        self.W_e1 = np.random.randn(self.input_dim, self.hidden_dim) * 0.1
        self.b_e1 = np.zeros(self.hidden_dim)
        self.W_mu = np.random.randn(self.hidden_dim, latent_dim) * 0.1
        self.b_mu = np.zeros(latent_dim)
        self.W_logvar = np.random.randn(self.hidden_dim, latent_dim) * 0.1
        self.b_logvar = np.zeros(latent_dim)

        # Decoder: [latent + cond] -> output
        self.W = np.random.randn(self.decoder_input_dim, self.state_dim) * 0.1
        self.b = np.zeros(self.state_dim)

        # === WGAN Critic weights ===
        # Critic: [state + cond] -> hidden(16) -> hidden(8) -> score(1)
        self.W_d1 = np.random.randn(self.input_dim, self.hidden_dim) * 0.1
        self.b_d1 = np.zeros(self.hidden_dim)
        self.W_d2 = np.random.randn(self.hidden_dim, self.hidden_dim // 2) * 0.1
        self.b_d2 = np.zeros(self.hidden_dim // 2)
        self.W_d3 = np.random.randn(self.hidden_dim // 2, 1) * 0.1
        self.b_d3 = np.zeros(1)

        # Adam optimizer state (shared across CVAE and Critic)
        self.m = {}
        self.v = {}
        self.t = 0

        self.trained = False

    # ── Condition helpers ──────────────────────────────────────────────

    def _make_condition(self, scenario_idx: int) -> np.ndarray:
        c = np.zeros(self.num_scenarios)
        c[scenario_idx % self.num_scenarios] = 1.0
        return c

    def _make_condition_batch(self, indices: np.ndarray) -> np.ndarray:
        batch = np.zeros((len(indices), self.num_scenarios))
        batch[np.arange(len(indices)), indices % self.num_scenarios] = 1.0
        return batch

    # ── CVAE forward / generation ──────────────────────────────────────

    def forward(self, latent: np.ndarray, condition: np.ndarray) -> np.ndarray:
        """Decoder forward pass: concat(latent, condition) -> output."""
        zc = np.concatenate([latent, condition], axis=-1)
        return np.tanh(zc @ self.W + self.b)

    def encode(self, x: np.ndarray, conditions: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Encoder forward pass. Returns (mu, log_var, z)."""
        x_cond = np.concatenate([x, conditions], axis=1)
        h1 = np.tanh(x_cond @ self.W_e1 + self.b_e1)
        mu = h1 @ self.W_mu + self.b_mu
        log_var = h1 @ self.W_logvar + self.b_logvar
        log_var = np.clip(log_var, -20.0, 20.0)
        std = np.exp(0.5 * log_var)
        eps = np.random.randn(*mu.shape)
        z = mu + eps * std
        return mu, log_var, z

    # ── WGAN Critic ────────────────────────────────────────────────────

    def critic_forward(self, x: np.ndarray, conditions: np.ndarray) -> np.ndarray:
        """Critic forward pass: [state + cond] -> score(1)."""
        xc = np.concatenate([x, conditions], axis=1)
        h1 = np.tanh(xc @ self.W_d1 + self.b_d1)
        h2 = np.tanh(h1 @ self.W_d2 + self.b_d2)
        score = h2 @ self.W_d3 + self.b_d3
        return score  # (batch, 1) — no sigmoid, WGAN uses raw scores

    def _critic_gradient_penalty(self, real: np.ndarray, fake: np.ndarray,
                                  conditions: np.ndarray) -> float:
        """WGAN-GP: penalize ||∇_x̂ critic(x̂)||_2 deviating from 1.

        Samples interpolated points between real and generated states and
        computes the L2 norm of the critic gradient w.r.t those points.
        """
        batch_size = len(real)
        alpha = np.random.rand(batch_size, 1)
        interp = alpha * real + (1 - alpha) * fake  # (batch, state_dim)

        # Forward pass through critic
        xc = np.concatenate([interp, conditions], axis=1)
        h1 = np.tanh(xc @ self.W_d1 + self.b_d1)
        h2 = np.tanh(h1 @ self.W_d2 + self.b_d2)
        score = h2 @ self.W_d3 + self.b_d3

        # Gradient of score w.r.t interp (the state input, not condition)
        # Chain rule: d_score/d_interp
        d_score = np.ones_like(score)  # (batch, 1)
        d_h2 = d_score @ self.W_d3.T  # (batch, 8)
        d_h1 = d_h2 * (1 - h2 ** 2)  # through tanh
        d_xc = (d_h1 @ self.W_d2.T) * (1 - h1 ** 2)  # through tanh
        # d_xc is (batch, input_dim); we only want gradient w.r.t state (first state_dim cols)
        grads = d_xc[:, :self.state_dim]  # (batch, state_dim)

        # Gradient penalty: (||grad||_2 - 1)^2, mean over batch
        grad_norm = np.sqrt(np.sum(grads ** 2, axis=1) + 1e-12)
        gp = np.mean((grad_norm - 1.0) ** 2)
        return float(gp)

    # ── synthesis ──────────────────────────────────────────────────────

    def synthesize_scenario(self, base_occupancy: float, base_price: float,
                            scenario_idx: Optional[int] = None) -> np.ndarray:
        """Generate a scenario-conditional state from the CVAE.

        When scenario_idx is None (backward compat), samples a random scenario.
        Returns [occupancy_rate, price, congestion, 0] vector.
        """
        if scenario_idx is None:
            scenario_idx = np.random.randint(self.num_scenarios)
        cond = self._make_condition(scenario_idx)
        z = np.random.randn(1, self.latent_dim)
        synthetic = self.forward(z, cond.reshape(1, -1)).flatten()

        occ_delta = float(synthetic[0]) * 0.3
        price_mult = float(synthetic[1]) * 0.5
        new_occ = np.clip(base_occupancy + occ_delta, 0, 1)
        new_price = np.clip(base_price * (1 + price_mult), 5, 50)
        congestion = float(synthetic[2])
        return np.array([new_occ, new_price, congestion])

    # ── Adam optimizer ─────────────────────────────────────────────────

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

    def _step_adam(self):
        """Increment Adam timestep (call once per batch)."""
        self.t += 1

    # ── CVAE training step ─────────────────────────────────────────────

    def train_step(self, real_samples: np.ndarray, lr: float = 0.001,
                   conditions: Optional[np.ndarray] = None) -> float:
        """Single CVAE training step: reconstruction + KL loss."""
        batch_size = len(real_samples)
        if batch_size == 0:
            return 0.0

        if real_samples.shape[1] < self.state_dim:
            padding = np.zeros((batch_size, self.state_dim - real_samples.shape[1]))
            x = np.hstack([real_samples, padding])
        else:
            x = real_samples[:, :self.state_dim]

        if conditions is None:
            cond_indices = np.random.randint(0, self.num_scenarios, size=batch_size)
            conditions = self._make_condition_batch(cond_indices)

        # Forward
        x_cond = np.concatenate([x, conditions], axis=1)
        h1 = np.tanh(x_cond @ self.W_e1 + self.b_e1)
        mu = h1 @ self.W_mu + self.b_mu
        log_var = h1 @ self.W_logvar + self.b_logvar
        log_var = np.clip(log_var, -20.0, 20.0)
        std = np.exp(0.5 * log_var)
        eps = np.random.randn(*mu.shape)
        z = mu + eps * std

        z_cond = np.concatenate([z, conditions], axis=1)
        fake = np.tanh(z_cond @ self.W + self.b)

        # Loss
        recon_loss = np.mean((fake - x) ** 2)
        kl_loss = -0.5 * np.mean(1 + log_var - mu**2 - np.exp(log_var))
        loss = recon_loss + self.kl_weight * kl_loss

        # Backward
        d_fake = 2 * (fake - x) / (batch_size * self.state_dim)
        d_dec_in = d_fake * (1 - fake ** 2)

        dW_z = z_cond.T @ d_dec_in
        db = np.sum(d_dec_in, axis=0)

        d_z_cond = d_dec_in @ self.W.T
        dz = d_z_cond[:, :self.latent_dim]

        d_mu = dz + (self.kl_weight * mu) / (batch_size * self.latent_dim)
        d_logvar_recon = dz * (0.5 * eps * std)
        d_logvar_kl = (self.kl_weight * (np.exp(log_var) - 1)) / (2 * batch_size * self.latent_dim)
        d_logvar = d_logvar_recon + d_logvar_kl

        dW_mu = h1.T @ d_mu
        db_mu = np.sum(d_mu, axis=0)
        dW_logvar = h1.T @ d_logvar
        db_logvar = np.sum(d_logvar, axis=0)

        dh1 = d_mu @ self.W_mu.T + d_logvar @ self.W_logvar.T
        dh1_in = dh1 * (1 - h1 ** 2)
        dW_e1 = x_cond.T @ dh1_in
        db_e1 = np.sum(dh1_in, axis=0)

        # Updates
        self._step_adam()
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

    # ── WGAN adversarial training step ─────────────────────────────────

    def wgan_train_step(self, real_samples: np.ndarray,
                        conditions: Optional[np.ndarray] = None,
                        lr_critic: float = 0.0005,
                        lr_gen: float = 0.0003) -> dict:
        """Alternating WGAN-GP training: critic self.n_critic times, generator once.

        Args:
            real_samples: (batch, 4) real state vectors
            conditions: (batch, num_scenarios) condition vectors
            lr_critic: learning rate for critic updates
            lr_gen: learning rate for generator (decoder) updates

        Returns:
            dict with critic_loss, gen_loss, gradient_penalty
        """
        batch_size = len(real_samples)
        if batch_size == 0:
            return {"critic_loss": 0.0, "gen_loss": 0.0, "gradient_penalty": 0.0}

        if real_samples.shape[1] < self.state_dim:
            padding = np.zeros((batch_size, self.state_dim - real_samples.shape[1]))
            x = np.hstack([real_samples, padding])
        else:
            x = real_samples[:, :self.state_dim]

        if conditions is None:
            cond_indices = np.random.randint(0, self.num_scenarios, size=batch_size)
            conditions = self._make_condition_batch(cond_indices)

        # Generate fake samples from the CVAE prior
        z = np.random.randn(batch_size, self.latent_dim)
        fake = self.forward(z, conditions)

        # ── Critic training (n_critic times) ──
        gp_vals = []
        critic_loss_vals = []

        for _ in range(self.n_critic):
            # Compute critic scores
            real_score = self.critic_forward(x, conditions)
            fake_score = self.critic_forward(fake, conditions)

            # Wasserstein loss: maximize E[real_score] - E[fake_score]
            # We minimize fake_score - real_score
            wasserstein = np.mean(fake_score - real_score)

            # Gradient penalty
            gp = self._critic_gradient_penalty(x, fake, conditions)
            gp_vals.append(gp)

            critic_loss = float(wasserstein) + self.lambda_gp * gp
            critic_loss_vals.append(critic_loss)

            # Backward: gradients of critic_loss w.r.t critic weights
            d_real = np.ones_like(real_score) / batch_size  # d(wasserstein)/d(real_score) = -1 * 1/batch for mean
            d_fake = -np.ones_like(fake_score) / batch_size  # d(wasserstein)/d(fake_score) = 1

            # We need gradient of wasserstein + gp * lambda through the critic.
            # wasserstein = mean(fake_score - real_score)
            # = mean(critic(fake)) - mean(critic(real))
            # d_wasserstein / d_params = d(mean(critic(fake)))/d_params - d(mean(critic(real)))/d_params

            # Gradient through critic for real samples
            # critic(real) = forward pass, we need d(mean(critic(real)))/d(W_d*, b_d*)
            xc_real = np.concatenate([x, conditions], axis=1)
            h1_real = np.tanh(xc_real @ self.W_d1 + self.b_d1)
            h2_real = np.tanh(h1_real @ self.W_d2 + self.b_d2)
            score_real = h2_real @ self.W_d3 + self.b_d3

            d_score_real = -np.ones_like(score_real) / batch_size  # -mean
            d_h2_real = d_score_real @ self.W_d3.T
            d_h1_real = d_h2_real * (1 - h2_real ** 2)
            d_xc_real = (d_h1_real @ self.W_d2.T) * (1 - h1_real ** 2)

            dW_d3_real = h2_real.T @ d_score_real
            db_d3_real = np.sum(d_score_real, axis=0)
            dW_d2_real = h1_real.T @ d_h1_real
            db_d2_real = np.sum(d_h1_real, axis=0)
            dW_d1_real = xc_real.T @ d_xc_real
            db_d1_real = np.sum(d_xc_real, axis=0)

            # Gradient through critic for fake samples
            xc_fake = np.concatenate([fake, conditions], axis=1)
            h1_fake = np.tanh(xc_fake @ self.W_d1 + self.b_d1)
            h2_fake = np.tanh(h1_fake @ self.W_d2 + self.b_d2)
            score_fake = h2_fake @ self.W_d3 + self.b_d3

            d_score_fake = np.ones_like(score_fake) / batch_size  # +mean
            d_h2_fake = d_score_fake @ self.W_d3.T
            d_h1_fake = d_h2_fake * (1 - h2_fake ** 2)
            d_xc_fake = (d_h1_fake @ self.W_d2.T) * (1 - h1_fake ** 2)

            dW_d3_fake = h2_fake.T @ d_score_fake
            db_d3_fake = np.sum(d_score_fake, axis=0)
            dW_d2_fake = h1_fake.T @ d_h1_fake
            db_d2_fake = np.sum(d_h1_fake, axis=0)
            dW_d1_fake = xc_fake.T @ d_xc_fake
            db_d1_fake = np.sum(d_xc_fake, axis=0)

            # === Gradient penalty gradient (approximate via stop-gradient on GP) ===
            # For a full gradient, we'd need second-order gradients through critic
            # which is complex in numpy. We approximate by computing GP contribution
            # through the interpolated path. This is a standard WGAN-GP training
            # signal even without the full hessian.
            #
            # We re-use the interpolated forward pass from _critic_gradient_penalty
            alpha = np.random.rand(batch_size, 1)
            interp = alpha * x + (1 - alpha) * fake

            xc_interp = np.concatenate([interp, conditions], axis=1)
            h1_i = np.tanh(xc_interp @ self.W_d1 + self.b_d1)
            h2_i = np.tanh(h1_i @ self.W_d2 + self.b_d2)
            score_i = h2_i @ self.W_d3 + self.b_d3

            d_score_i = np.ones_like(score_i)
            d_h2_i = d_score_i @ self.W_d3.T
            d_h1_i = d_h2_i * (1 - h2_i ** 2)
            d_xc_i = (d_h1_i @ self.W_d2.T) * (1 - h1_i ** 2)
            grads_i = d_xc_i[:, :self.state_dim]
            grad_norm_i = np.sqrt(np.sum(grads_i ** 2, axis=1) + 1e-12)

            # GP = mean((||grad|| - 1)^2)
            # d_gp / d_params involves second-order Jacobian of critic
            # We use the "1-centered gradient penalty" formulation which
            # gives: d_gp ~= 2 * (||grad|| - 1) / ||grad|| * grad * d_grad/d_params
            # For simplicity, we approximate: GP influences critic via the
            # interpolated path's contribution to the critic weights.
            gp_coeff = 2.0 * (grad_norm_i - 1.0) / (grad_norm_i + 1e-12)  # (batch,)
            gp_coeff = gp_coeff.reshape(-1, 1)  # (batch, 1)

            # GP gradient: pass through the interpolated path
            dW_d3_interp = h2_i.T @ (d_score_i * gp_coeff * self.lambda_gp / batch_size)
            db_d3_interp = np.sum(d_score_i * gp_coeff * self.lambda_gp / batch_size, axis=0)

            d_h2_interp = (d_score_i * gp_coeff * self.lambda_gp / batch_size) @ self.W_d3.T
            d_h1_interp = d_h2_interp * (1 - h2_i ** 2)
            d_xc_interp = (d_h1_interp @ self.W_d2.T) * (1 - h1_i ** 2)

            dW_d2_interp = h1_i.T @ d_h1_interp
            db_d2_interp = np.sum(d_h1_interp, axis=0)
            dW_d1_interp = xc_interp.T @ d_xc_interp
            db_d1_interp = np.sum(d_xc_interp, axis=0)

            # Combine all gradients
            dW_d1_total = dW_d1_real + dW_d1_fake + dW_d1_interp
            db_d1_total = db_d1_real + db_d1_fake + db_d1_interp
            dW_d2_total = dW_d2_real + dW_d2_fake + dW_d2_interp
            db_d2_total = db_d2_real + db_d2_fake + db_d2_interp
            dW_d3_total = dW_d3_real + dW_d3_fake + dW_d3_interp
            db_d3_total = db_d3_real + db_d3_fake + db_d3_interp

            # Adam update for critic
            self._step_adam()
            self.W_d1 = self._adam_update("W_d1", self.W_d1, dW_d1_total, lr_critic)
            self.b_d1 = self._adam_update("b_d1", self.b_d1, db_d1_total, lr_critic)
            self.W_d2 = self._adam_update("W_d2", self.W_d2, dW_d2_total, lr_critic)
            self.b_d2 = self._adam_update("b_d2", self.b_d2, db_d2_total, lr_critic)
            self.W_d3 = self._adam_update("W_d3", self.W_d3, dW_d3_total, lr_critic)
            self.b_d3 = self._adam_update("b_d3", self.b_d3, db_d3_total, lr_critic)

            # Regenerate fake for next critic iteration (generator hasn't changed yet)
            z = np.random.randn(batch_size, self.latent_dim)
            fake = self.forward(z, conditions)

        # ── Generator (decoder) training ──
        # Train the decoder to fool the critic: maximize critic(fake)
        z = np.random.randn(batch_size, self.latent_dim)
        fake = self.forward(z, conditions)
        fake_score = self.critic_forward(fake, conditions)
        gen_loss = -np.mean(fake_score)  # minimize -critic(fake)

        # ── Generator (decoder) training ──
        # Train the decoder to fool the critic: maximize critic(fake)
        z_gen = np.random.randn(batch_size, self.latent_dim)
        z_cond_gen = np.concatenate([z_gen, conditions], axis=1)
        fake_gen = np.tanh(z_cond_gen @ self.W + self.b)
        fake_score_gen = self.critic_forward(fake_gen, conditions)
        gen_loss = -np.mean(fake_score_gen)

        # Backward: d(gen_loss) / d(decoder params)
        # Through critic: score = critic(fake, cond), we need d(score)/d(fake)
        xc_fg = np.concatenate([fake_gen, conditions], axis=1)
        h1_fg = np.tanh(xc_fg @ self.W_d1 + self.b_d1)
        h2_fg = np.tanh(h1_fg @ self.W_d2 + self.b_d2)
        d_score = -np.ones_like(fake_score_gen) / batch_size
        d_h2_fg = d_score @ self.W_d3.T
        d_h1_fg = d_h2_fg * (1 - h2_fg ** 2)
        d_fake_fg = (d_h1_fg @ self.W_d2.T) * (1 - h1_fg ** 2)
        d_fake_fg = d_fake_fg[:, :self.state_dim]

        # Through decoder: fake = tanh(z_cond @ W + b)
        d_dec_in = d_fake_fg * (1 - fake_gen ** 2)
        dW_gen = z_cond_gen.T @ d_dec_in
        db_gen = np.sum(d_dec_in, axis=0)

        self._step_adam()
        self.W = self._adam_update("W", self.W, dW_gen, lr_gen)
        self.b = self._adam_update("b", self.b, db_gen, lr_gen)

        avg_gp = float(np.mean(gp_vals)) if gp_vals else 0.0
        avg_critic_loss = float(np.mean(critic_loss_vals)) if critic_loss_vals else 0.0
        gen_loss_val = float(gen_loss) if isinstance(gen_loss, np.ndarray) else float(gen_loss)

        self.trained = True
        return {
            "critic_loss": avg_critic_loss,
            "gen_loss": gen_loss_val,
            "gradient_penalty": avg_gp,
        }

    def train(self, real_data: np.ndarray, epochs: int = 500,
              wgan_epochs: int = 0) -> List[float]:
        """Train the CVAE, optionally followed by WGAN adversarial fine-tuning.

        Args:
            real_data: (N, 4+) training data.
            epochs: CVAE pre-training epochs.
            wgan_epochs: WGAN adversarial fine-tuning epochs (0 = skip).

        Returns:
            List of logged loss values during CVAE training.
        """
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
        logger.info("Generator CVAE trained: %d steps", epochs)

        # WGAN fine-tuning
        if wgan_epochs > 0:
            logger.info("Starting WGAN fine-tuning for %d epochs", wgan_epochs)
            for ep in range(wgan_epochs):
                idx = np.random.choice(len(real_data), min(32, len(real_data)), replace=False)
                batch = real_data[idx]
                target = batch[:, :self.state_dim]
                result = self.wgan_train_step(target)
                if (ep + 1) % 50 == 0:
                    logger.info("WGAN epoch %d/%d: critic=%.4f gen=%.4f gp=%.4f",
                                ep + 1, wgan_epochs,
                                result["critic_loss"], result["gen_loss"], result["gradient_penalty"])
            logger.info("WGAN fine-tuning complete: %d epochs", wgan_epochs)

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
            self._wgan_online_steps = 0
        self._online_buffer.append(sample)

        batch_size = int(os.getenv("ONLINE_BATCH_SIZE", "10"))
        if len(self._online_buffer) >= batch_size:
            batch = np.vstack(self._online_buffer)
            null_cond = np.zeros((batch_size, self.num_scenarios))

            # CVAE update
            cvae_loss = self.train_step(batch, lr=learning_rate, conditions=null_cond)
            self._online_steps += 1

            # WGAN update (every other online step) — alternates to save compute
            wgan_metrics = {}
            if self._online_steps % 2 == 0:
                wgan_metrics = self.wgan_train_step(batch, conditions=null_cond,
                                                     lr_critic=learning_rate * 0.5,
                                                     lr_gen=learning_rate * 0.3)
                self._wgan_online_steps += 1

            self._online_buffer = []
            logger.info("generator.online_update batch=%d cvae=%.6f wgan=%s total_steps=%d",
                        batch_size, cvae_loss,
                        wgan_metrics.get("gen_loss", "N/A"), self._online_steps)
            return {
                "trained": True, "samples": batch_size,
                "cvae_loss": cvae_loss,
                "wgan": wgan_metrics,
                "total_steps": self._online_steps,
            }

        return {"trained": False, "samples": len(self._online_buffer),
                "cvae_loss": None, "wgan": None, "total_steps": self._online_steps}
