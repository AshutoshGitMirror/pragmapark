import numpy as np
import logging
import random
import os


logger = logging.getLogger(__name__)

SEED = int(os.getenv("PRAGMA_SEED", "42"))
random.seed(SEED)
np.random.seed(SEED)

SCENARIO_NAMES = [
    "zone_closure", "price_surge", "capacity_expansion",
    "weather_disruption", "holiday_spike",
]


class Generator:
    """CVAE-WGAN for parking scenario generation.

    Encoder: [state(4)+cond(N)]→h16→mu(8)+logvar(8)
    Decoder: [latent(8)+cond(N)]→out(4)  (tanh)
    Critic:  [state(4)+cond(N)]→h16→h8→score(1)"""

    def __init__(self, latent_dim=8, kl_weight=0.05, num_scenarios=5,
                 lambda_gp=10.0, n_critic=3):
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

        # Encoder
        self.W_e1 = np.random.randn(self.input_dim, self.hidden_dim) * 0.1
        self.b_e1 = np.zeros(self.hidden_dim)
        self.W_mu = np.random.randn(self.hidden_dim, latent_dim) * 0.1
        self.b_mu = np.zeros(latent_dim)
        self.W_logvar = np.random.randn(self.hidden_dim, latent_dim) * 0.1
        self.b_logvar = np.zeros(latent_dim)

        # Decoder
        self.W = np.random.randn(self.decoder_input_dim, self.state_dim) * 0.1
        self.b = np.zeros(self.state_dim)

        # WGAN Critic
        self.W_d1 = np.random.randn(self.input_dim, self.hidden_dim) * 0.1
        self.b_d1 = np.zeros(self.hidden_dim)
        self.W_d2 = np.random.randn(self.hidden_dim, 8) * 0.1
        self.b_d2 = np.zeros(8)
        self.W_d3 = np.random.randn(8, 1) * 0.1
        self.b_d3 = np.zeros(1)

        self.m, self.v = {}, {}
        self.t = 0
        self.trained = False

    def _make_cond(self, idx):
        c = np.zeros(self.num_scenarios)
        c[idx % self.num_scenarios] = 1.0
        return c

    def _make_cond_batch(self, indices):
        b = np.zeros((len(indices), self.num_scenarios))
        b[np.arange(len(indices)), indices % self.num_scenarios] = 1.0
        return b

    def forward(self, latent, condition):
        zc = np.concatenate([latent, condition], axis=-1)
        return np.tanh(zc @ self.W + self.b)

    def encode(self, x, conditions):
        xc = np.concatenate([x, conditions], axis=1)
        h1 = np.tanh(xc @ self.W_e1 + self.b_e1)
        mu = h1 @ self.W_mu + self.b_mu
        lv = np.clip(h1 @ self.W_logvar + self.b_logvar, -20, 20)
        z = mu + np.random.randn(*mu.shape) * np.exp(0.5 * lv)
        return mu, lv, z

    def critic_forward(self, x, conditions):
        xc = np.concatenate([x, conditions], axis=1)
        h1 = np.tanh(xc @ self.W_d1 + self.b_d1)
        h2 = np.tanh(h1 @ self.W_d2 + self.b_d2)
        return h2 @ self.W_d3 + self.b_d3

    def _critic_gradient_penalty(self, real, fake, conditions):
        bs = len(real)
        alpha = np.random.rand(bs, 1)
        interp = alpha * real + (1 - alpha) * fake
        xc = np.concatenate([interp, conditions], axis=1)
        h1 = np.tanh(xc @ self.W_d1 + self.b_d1)
        h2 = np.tanh(h1 @ self.W_d2 + self.b_d2)
        _ = h2 @ self.W_d3 + self.b_d3
        d_h2 = np.ones((bs, 1)) @ self.W_d3.T
        d_xc = (d_h2 * (1 - h2 ** 2) @ self.W_d2.T) * (1 - h1 ** 2)
        grads = d_xc[:, : self.state_dim]
        gn = np.sqrt(np.sum(grads ** 2, axis=1) + 1e-12)
        return float(np.mean((gn - 1.0) ** 2))

    def synthesize_scenario(self, base_occ, base_price, scenario_idx=None):
        if scenario_idx is None:
            scenario_idx = np.random.randint(self.num_scenarios)
        cond = self._make_cond(scenario_idx)
        z = np.random.randn(1, self.latent_dim)
        syn = self.forward(z, cond.reshape(1, -1)).flatten()
        occ = np.clip(base_occ + float(syn[0]) * 0.3, 0, 1)
        price = np.clip(base_price * (1 + float(syn[1]) * 0.5), 5, 50)
        return np.array([occ, price, float(syn[2])])

    def _adam_update(self, name, param, grad, lr):
        if name not in self.m:
            self.m[name] = np.zeros_like(param)
            self.v[name] = np.zeros_like(param)
        self.m[name] = 0.9 * self.m[name] + 0.1 * grad
        self.v[name] = 0.999 * self.v[name] + 0.001 * (grad ** 2)
        mh = self.m[name] / (1 - 0.9 ** self.t)
        vh = self.v[name] / (1 - 0.999 ** self.t)
        return param - lr * mh / (np.sqrt(vh) + 1e-8)

    def _step_adam(self):
        self.t += 1

    def _pad_state(self, x):
        if x.shape[1] < self.state_dim:
            return np.hstack(
                [x, np.zeros((len(x), self.state_dim - x.shape[1]))])
        return x[:, :self.state_dim]

    def train_step(self, real_samples, lr=0.001, conditions=None):
        bs = len(real_samples)
        if bs == 0:
            return 0.0
        x = self._pad_state(real_samples)
        if conditions is None:
            conditions = self._make_cond_batch(
                np.random.randint(0, self.num_scenarios, bs))

        xc = np.concatenate([x, conditions], axis=1)
        h1 = np.tanh(xc @ self.W_e1 + self.b_e1)
        mu = h1 @ self.W_mu + self.b_mu
        lv = np.clip(h1 @ self.W_logvar + self.b_logvar, -20, 20)
        z = mu + np.random.randn(*mu.shape) * np.exp(0.5 * lv)
        fake = np.tanh(np.concatenate(
            [z, conditions], axis=1) @ self.W + self.b)

        recon = np.mean((fake - x) ** 2)
        kl = -0.5 * np.mean(1 + lv - mu ** 2 - np.exp(lv))
        loss = recon + self.kl_weight * kl

        # Backward
        d_fake = 2 * (fake - x) / (bs * self.state_dim)
        d_dec_in = d_fake * (1 - fake ** 2)
        zc = np.concatenate([z, conditions], axis=1)
        dW = zc.T @ d_dec_in
        db = np.sum(d_dec_in, axis=0)
        dz = (d_dec_in @ self.W.T)[:, :self.latent_dim]
        d_mu = dz + (self.kl_weight * mu) / (bs * self.latent_dim)
        d_lv_recon = dz * 0.5 * np.random.randn(*mu.shape) * np.exp(0.5 * lv)
        d_lv_kl = (self.kl_weight * (np.exp(lv) - 1)) / \
            (2 * bs * self.latent_dim)
        d_lv = d_lv_recon + d_lv_kl
        dh1 = (d_mu @ self.W_mu.T + d_lv @ self.W_logvar.T) * (1 - h1 ** 2)
        dW_e1 = xc.T @ dh1

        self._step_adam()
        self.W_e1 = self._adam_update("W_e1", self.W_e1, dW_e1, lr)
        self.b_e1 = self._adam_update("b_e1", self.b_e1, np.sum(dh1, 0), lr)
        self.W_mu = self._adam_update("W_mu", self.W_mu, h1.T @ d_mu, lr)
        self.b_mu = self._adam_update("b_mu", self.b_mu, np.sum(d_mu, 0), lr)
        self.W_logvar = self._adam_update(
            "W_logvar", self.W_logvar, h1.T @ d_lv, lr)
        self.b_logvar = self._adam_update(
            "b_logvar", self.b_logvar, np.sum(d_lv, 0), lr)
        self.W = self._adam_update("W", self.W, dW, lr)
        self.b = self._adam_update("b", self.b, db, lr)
        self.trained = True
        return float(loss)

    def wgan_train_step(self, real_samples, conditions=None,
                        lr_critic=0.0005, lr_gen=0.0003):
        bs = len(real_samples)
        if bs == 0:
            return {"critic_loss": 0.0, "gen_loss": 0.0,
                    "gradient_penalty": 0.0}
        x = self._pad_state(real_samples)
        if conditions is None:
            conditions = self._make_cond_batch(
                np.random.randint(0, self.num_scenarios, bs))

        def _critic_grad(x_in, sign):
            xc = np.concatenate([x_in, conditions], axis=1)
            h1 = np.tanh(xc @ self.W_d1 + self.b_d1)
            h2 = np.tanh(h1 @ self.W_d2 + self.b_d2)
            d = sign * np.ones((bs, 1)) / bs
            dh2 = d @ self.W_d3.T
            dh1 = dh2 * (1 - h2 ** 2)
            dxc = (dh1 @ self.W_d2.T) * (1 - h1 ** 2)
            return (h2.T @ d, np.sum(d, 0), h1.T @ dh1, np.sum(dh1, 0),
                    xc.T @ dxc, np.sum(dxc, 0))

        gp_vals, c_losses = [], []
        for _ in range(self.n_critic):
            z = np.random.randn(bs, self.latent_dim)
            fake = self.forward(z, conditions)
            dW3_r, db3_r, dW2_r, db2_r, dW1_r, db1_r = _critic_grad(x, -1)
            dW3_f, db3_f, dW2_f, db2_f, dW1_f, db1_f = _critic_grad(fake, 1)
            gp = self._critic_gradient_penalty(x, fake, conditions)
            gp_vals.append(gp)
            c_losses.append(float(np.mean(fake - x)) + self.lambda_gp * gp)

            alpha = np.random.rand(bs, 1)
            interp = alpha * x + (1 - alpha) * fake
            xc_i = np.concatenate([interp, conditions], axis=1)
            h1_i = np.tanh(xc_i @ self.W_d1 + self.b_d1)
            h2_i = np.tanh(h1_i @ self.W_d2 + self.b_d2)
            d_i = np.ones((bs, 1))
            dh2_i = d_i @ self.W_d3.T
            dxc_i = (dh2_i * (1 - h2_i ** 2) @ self.W_d2.T) * (1 - h1_i ** 2)
            gn = np.sqrt(np.sum(dxc_i[:, :self.state_dim] ** 2, 1) + 1e-12)
            gpc = (2 * (gn - 1) / (gn + 1e-12)).reshape(-1, 1)
            factor = gpc * self.lambda_gp / bs
            dW3_i = h2_i.T @ (d_i * factor)
            db3_i = np.sum(d_i * factor, 0)
            dh2_i_2 = (d_i * factor) @ self.W_d3.T
            dh1_i_2 = dh2_i_2 * (1 - h2_i ** 2)
            dxc_i_2 = (dh1_i_2 @ self.W_d2.T) * (1 - h1_i ** 2)
            self._step_adam()
            self.W_d1 = self._adam_update(
                "W_d1", self.W_d1, dW1_r + dW1_f + xc_i.T @ dxc_i_2, lr_critic)
            self.b_d1 = self._adam_update(
                "b_d1", self.b_d1, db1_r + db1_f + np.sum(dxc_i_2, 0), lr_critic)
            self.W_d2 = self._adam_update(
                "W_d2", self.W_d2, dW2_r + dW2_f + h1_i.T @ dh1_i_2, lr_critic)
            self.b_d2 = self._adam_update(
                "b_d2", self.b_d2, db2_r + db2_f + np.sum(dh1_i_2, 0), lr_critic)
            self.W_d3 = self._adam_update(
                "W_d3", self.W_d3, dW3_r + dW3_f + dW3_i, lr_critic)
            self.b_d3 = self._adam_update(
                "b_d3", self.b_d3, db3_r + db3_f + db3_i, lr_critic)

        # Generator step
        z = np.random.randn(bs, self.latent_dim)
        fg = self.forward(z, conditions)
        fs = self.critic_forward(fg, conditions)
        gl = -np.mean(fs)
        xc = np.concatenate([fg, conditions], axis=1)
        h1 = np.tanh(xc @ self.W_d1 + self.b_d1)
        dh2 = (-np.ones_like(fs) / bs) @ self.W_d3.T
        dfg = (dh2 * (1 - np.tanh(h1 @ self.W_d2 + self.b_d2) ** 2)
               @ self.W_d2.T) * (1 - h1 ** 2)
        dfg = dfg[:, :self.state_dim]
        d_dec = dfg * (1 - fg ** 2)
        zc = np.concatenate([z, conditions], axis=1)
        self._step_adam()
        self.W = self._adam_update("W", self.W, zc.T @ d_dec, lr_gen)
        self.b = self._adam_update("b", self.b, np.sum(d_dec, 0), lr_gen)

        self.trained = True
        return {"critic_loss": float(np.mean(c_losses)) if c_losses else 0,
                "gen_loss": float(gl), "gradient_penalty": float(np.mean(gp_vals)) if gp_vals else 0}

    def train(self, real_data, epochs=500, wgan_epochs=0):
        epochs = min(epochs, 1000)
        losses = []
        for ep in range(epochs):
            idx = np.random.choice(len(real_data), min(
                32, len(real_data)), replace=False)
            loss = self.train_step(real_data[idx][:, :self.state_dim])
            if (ep + 1) % 100 == 0:
                losses.append(loss)
                logger.info("CVAE epoch %d/%d: loss=%.4f",
                            ep + 1, epochs, loss)
        logger.info("CVAE trained: %d steps", epochs)
        for ep in range(wgan_epochs):
            idx = np.random.choice(len(real_data), min(
                32, len(real_data)), replace=False)
            r = self.wgan_train_step(real_data[idx][:, :self.state_dim])
            if (ep + 1) % 50 == 0:
                logger.info("WGAN %d/%d: c=%.4f g=%.4f gp=%.4f",
                            ep + 1, wgan_epochs, r["critic_loss"], r["gen_loss"], r["gradient_penalty"])
        self.trained = True
        return losses

    def online_update(self, occ_rate, price, duration_hours,
                      congestion="normal", lr=0.0005):
        cmap = {"normal": 0.0, "moderate": 0.33, "high": 0.66, "critical": 1.0}
        sample = np.array([[
            float(np.clip(occ_rate, 0, 1)),
            float(np.clip(price / 50.0, 0, 1)),
            cmap.get(congestion, 0.0),
            float(np.clip(duration_hours / 24.0, 0, 1)),
        ]])
        if not hasattr(self, '_online_buffer'):
            self._online_buffer = []
            self._online_steps = 0
            self._wgan_online_steps = 0
        self._online_buffer.append(sample)
        bs = int(os.getenv("ONLINE_BATCH_SIZE", "10"))
        if len(self._online_buffer) >= bs:
            batch = np.vstack(self._online_buffer)
            nc = np.zeros((bs, self.num_scenarios))
            c_loss = self.train_step(batch, lr=lr, conditions=nc)
            self._online_steps += 1
            wg = {}
            if self._online_steps % 2 == 0:
                wg = self.wgan_train_step(
                    batch, conditions=nc, lr_critic=lr * 0.5, lr_gen=lr * 0.3)
                self._wgan_online_steps += 1
            self._online_buffer = []
            return {"trained": True, "samples": bs, "cvae_loss": c_loss,
                    "wgan": wg, "total_steps": self._online_steps}
        return {"trained": False, "samples": len(self._online_buffer), "cvae_loss": None,
                "wgan": None, "total_steps": self._online_steps}
