import numpy as np
import random
from collections import deque
from src.constants import (
    HIGH_OCCUPANCY_THRESHOLD, LOW_OCCUPANCY_THRESHOLD,
    ACTION_MIN, ACTION_MAX,
)

AGENT_HIGH_ACTION = 0.2
AGENT_LOW_ACTION = -0.1
AGENT_NEUTRAL_ACTION = 0.0


class _ModelCompat:
    """Backward-compat wrapper: agent.model.predict(x) delegates to NumPy MLP."""

    def __init__(self, agent: "NeuralAgent"):
        self._agent = agent

    def predict(self, x: np.ndarray) -> np.ndarray:
        q, _ = self._agent._forward(x, self._agent._params())
        return q

    def fit(self, X: np.ndarray, y: np.ndarray) -> "_ModelCompat":
        pred, cache = self._agent._forward(X, self._agent._params())
        grads = self._agent._backward(pred - y.reshape(-1, 1), cache)
        self._agent._adam_update(grads, self._agent.lr)
        self._agent.is_fitted = True
        return self


class NeuralAgent:
    """NumPy DQN agent: 3-layer MLP (64x64), Adam, experience replay, target network.

    State: [occupancy, price, vehicle_ratio, resident_share_ratio] — 4-dim.
    """

    def __init__(self, state_size=4, action_size=1):
        self.input_dim = state_size + action_size
        self.state_size = state_size
        self.action_size = action_size
        self.hidden = 64
        self.lr = 0.001

        self.W1 = np.random.randn(
            self.input_dim, self.hidden) * np.sqrt(2.0 / self.input_dim)
        self.b1 = np.zeros(self.hidden)
        self.W2 = np.random.randn(
            self.hidden, self.hidden) * np.sqrt(2.0 / self.hidden)
        self.b2 = np.zeros(self.hidden)
        self.W3 = np.random.randn(self.hidden, 1) * np.sqrt(2.0 / self.hidden)
        self.b3 = np.zeros(1)
        self._sync_target()

        self._t = 0
        self._adam = {n: {"m": np.zeros_like(getattr(self, n)),
                          "v": np.zeros_like(getattr(self, n))}
                      for n in ("W1", "b1", "W2", "b2", "W3", "b3")}

        self.epsilon = 1.0
        self.epsilon_decay = 0.98
        self.epsilon_min = 0.05
        self.gamma = 0.95
        self.memory = deque(maxlen=2000)
        self.batch_size = 128
        self.target_update_freq = 20
        self.update_counter = 0
        self.is_fitted = False

    def _params(self, target=False):
        pfx = "t" if target else ""
        return {n: getattr(self, f"{pfx}{n}")
                for n in ("W1", "b1", "W2", "b2", "W3", "b3")}

    def _sync_target(self):
        for n in ("W1", "b1", "W2", "b2", "W3", "b3"):
            setattr(self, f"t{n}", getattr(self, n).copy())

    @staticmethod
    def _relu(x):
        return np.maximum(0, x)

    def _forward(self, x, params):
        z1 = x @ params["W1"] + params["b1"]
        h1 = self._relu(z1)
        z2 = h1 @ params["W2"] + params["b2"]
        h2 = self._relu(z2)
        return h2 @ params["W3"] + params["b3"], (x, z1, h1, z2, h2)

    def _backward(self, grad, cache):
        x, z1, h1, z2, h2 = cache
        return {
            "W3": h2.T @ grad,
            "b3": grad.sum(axis=0),
            "W2": h1.T @ ((grad @ self.W3.T) * (z2 > 0)),
            "b2": ((grad @ self.W3.T) * (z2 > 0)).sum(axis=0),
            "W1": x.T @ ((((grad @ self.W3.T) * (z2 > 0)) @ self.W2.T) * (z1 > 0)),
            "b1": ((((grad @ self.W3.T) * (z2 > 0)) @ self.W2.T) * (z1 > 0)).sum(axis=0),
        }

    def _adam_update(self, grads, lr):
        self._t += 1
        b1, b2 = 0.9, 0.999
        for name in ("W1", "b1", "W2", "b2", "W3", "b3"):
            g = grads[name]
            s = self._adam[name]
            s["m"] = b1 * s["m"] + (1 - b1) * g
            s["v"] = b2 * s["v"] + (1 - b2) * (g ** 2)
            mh = s["m"] / (1 - b1 ** self._t)
            vh = s["v"] / (1 - b2 ** self._t)
            setattr(self, name, getattr(self, name) -
                    lr * mh / (np.sqrt(vh) + 1e-8))

    def _scale_state(self, state):
        s = state.flatten() if hasattr(
            state, "ndim") and state.ndim > 1 else np.asarray(state).flatten()
        s[1] = s[1] / 50.0
        return s

    def _predict_q(self, params, scaled_s, action):
        q, _ = self._forward(
            np.append(scaled_s, action).reshape(1, -1), params)
        return float(q[0, 0])

    def _max_q(self, params, scaled_ns, n_candidates=10):
        candidates = np.linspace(ACTION_MIN, ACTION_MAX, n_candidates)
        xs = np.column_stack(
            [np.tile(scaled_ns, (n_candidates, 1)), candidates])
        qs, _ = self._forward(xs, params)
        return float(np.max(qs))

    def decay_epsilon(self):
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay

    def act(self, state, train=True):
        s = state.flatten() if hasattr(
            state, "ndim") and state.ndim > 1 else np.asarray(state).flatten()
        if train and np.random.rand() <= self.epsilon:
            return np.random.uniform(ACTION_MIN, ACTION_MAX)
        if not self.is_fitted:
            occ = float(s[0])
            if occ > HIGH_OCCUPANCY_THRESHOLD:
                return AGENT_HIGH_ACTION
            if occ < LOW_OCCUPANCY_THRESHOLD:
                return AGENT_LOW_ACTION
            return AGENT_NEUTRAL_ACTION
        ss = self._scale_state(s)
        candidates = np.linspace(ACTION_MIN, ACTION_MAX, 10)
        xs = np.column_stack([np.tile(ss, (10, 1)), candidates])
        qs, _ = self._forward(xs, self._params())
        return candidates[np.argmax(qs[:, 0])]

    def train(self, state, action, reward, next_state, done):
        s = state.flatten() if hasattr(
            state, "ndim") and state.ndim > 1 else np.asarray(state).flatten()
        ns = next_state.flatten() if hasattr(
            next_state, "ndim") and next_state.ndim > 1 else np.asarray(next_state).flatten()
        self.memory.append((s, action, reward, ns, done))
        if len(self.memory) <= 64:
            return
        batch = random.sample(list(self.memory), min(
            len(self.memory), self.batch_size))
        X, y = [], []
        for s_, a, r, ns_, d in batch:
            ss = self._scale_state(s_)
            sn = self._scale_state(ns_)
            target = r if d else (
                r + self.gamma * self._max_q(self._params(target=True), sn) if self.is_fitted else r)
            X.append(np.append(ss, a))
            y.append(target)
        pred, cache = self._forward(np.array(X), self._params())
        self._adam_update(self._backward(
            pred - np.array(y).reshape(-1, 1), cache), self.lr)
        self.is_fitted = True
        self.update_counter += 1
        if self.update_counter % self.target_update_freq == 0:
            self._sync_target()

    @property
    def model(self):
        return _ModelCompat(self)

    @model.setter
    def model(self, _value):
        pass
