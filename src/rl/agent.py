import numpy as np
import random
from collections import deque
from copy import deepcopy
from src.constants import HIGH_OCCUPANCY_THRESHOLD, LOW_OCCUPANCY_THRESHOLD, ACTION_MIN, ACTION_MAX

AGENT_HIGH_ACTION = 0.2
AGENT_LOW_ACTION = -0.1
AGENT_NEUTRAL_ACTION = 0.0


class _ModelCompat:
    """Backward-compatible wrapper so existing code like agent.model.predict(x) works.

    Used by multi_agent.py:_compute_agent_qs() and train_control.py:train_neural_control().
    Delegates to the NumPy network's forward/backward methods.
    """

    def __init__(self, agent: 'NeuralAgent'):
        self._agent = agent

    def predict(self, x: np.ndarray) -> np.ndarray:
        """agent.model.predict(x) -> Q-value prediction. x shape: (N, input_dim)."""
        q, _ = self._agent._forward(x, self._agent._params())
        return q

    def fit(self, X: np.ndarray, y: np.ndarray) -> '_ModelCompat':
        """agent.model.fit(X, y) -> single gradient descent step. Used by warm-start."""
        pred, cache = self._agent._forward(X, self._agent._params())
        grad = pred - y.reshape(-1, 1)
        grads = self._agent._backward(grad, cache)
        self._agent._adam_update(grads, self._agent.lr)
        self._agent.is_fitted = True
        return self


class NeuralAgent:
    """Deep Q-Network (DQN) agent implemented entirely in NumPy.

    Replaces sklearn MLPRegressor with a hand-written 3-layer MLP
    (64 → 64 → 1, ReLU, Adam) that performs proper DQN learning with
    experience replay, target network, and epsilon-greedy exploration.

    Paper alignment (Piccialli et al. 2025): 'The DQN agent learns
    optimal pricing policies through deep Q-learning with experience
    replay and target network stabilization.'
    """

    def __init__(self, state_size: int = 3, action_size: int = 1):
        self.input_dim = state_size + action_size  # state + action concatenated
        self.state_size = state_size
        self.action_size = action_size
        self.hidden = 64
        self.lr = 0.001

        # ---------- Online network (3-layer MLP) ----------
        # He initialization for ReLU: std = sqrt(2 / fan_in)
        self.W1 = np.random.randn(self.input_dim, self.hidden) * np.sqrt(2.0 / self.input_dim)
        self.b1 = np.zeros(self.hidden)
        self.W2 = np.random.randn(self.hidden, self.hidden) * np.sqrt(2.0 / self.hidden)
        self.b2 = np.zeros(self.hidden)
        self.W3 = np.random.randn(self.hidden, 1) * np.sqrt(2.0 / self.hidden)
        self.b3 = np.zeros(1)

        # ---------- Target network (frozen copy, periodically synced) ----------
        self._sync_target()

        # ---------- Adam optimizer state (per parameter) ----------
        self._t = 0
        self._adam: dict = {}
        for name in ('W1', 'b1', 'W2', 'b2', 'W3', 'b3'):
            v = getattr(self, name)
            self._adam[name] = {'m': np.zeros_like(v), 'v': np.zeros_like(v)}

        # ---------- DQL hyper-parameters ----------
        self.epsilon = 1.0
        self.epsilon_decay = 0.98
        self.epsilon_min = 0.05
        self.gamma = 0.95
        self.memory: deque = deque(maxlen=2000)
        self.batch_size = 128
        self.target_update_freq = 20
        self.update_counter = 0
        self.is_fitted = False

    # ------------------------------------------------------------------
    # Network helpers
    # ------------------------------------------------------------------

    def _params(self, target: bool = False) -> dict:
        prefix = 't' if target else ''
        return {
            'W1': getattr(self, f'{prefix}W1'),
            'b1': getattr(self, f'{prefix}b1'),
            'W2': getattr(self, f'{prefix}W2'),
            'b2': getattr(self, f'{prefix}b2'),
            'W3': getattr(self, f'{prefix}W3'),
            'b3': getattr(self, f'{prefix}b3'),
        }

    def _sync_target(self):
        """Hard-copy online weights → target network."""
        self.tW1 = self.W1.copy()
        self.tb1 = self.b1.copy()
        self.tW2 = self.W2.copy()
        self.tb2 = self.b2.copy()
        self.tW3 = self.W3.copy()
        self.tb3 = self.b3.copy()

    # ------------------------------------------------------------------
    # Forward / Backward
    # ------------------------------------------------------------------

    @staticmethod
    def _relu(x: np.ndarray) -> np.ndarray:
        return np.maximum(0, x)

    def _forward(self, x: np.ndarray, params: dict):
        """Forward pass through 3-layer MLP.

        Args:
            x: Input of shape (N, input_dim).
            params: Parameter dict (online or target).

        Returns:
            q: Q-values of shape (N, 1).
            cache: Tuple for backward pass.
        """
        z1 = x @ params['W1'] + params['b1']          # (N, 64)
        h1 = self._relu(z1)
        z2 = h1 @ params['W2'] + params['b2']          # (N, 64)
        h2 = self._relu(z2)
        q = h2 @ params['W3'] + params['b3']           # (N, 1)
        return q, (x, z1, h1, z2, h2)

    def _backward(self, grad: np.ndarray, cache: tuple) -> dict:
        """Manual backpropagation through the MLP.

        Args:
            grad: dL/d_output, shape (N, 1).
            cache: (x, z1, h1, z2, h2) from forward.

        Returns:
            Gradient dict matching _params() keys.
        """
        x, z1, h1, z2, h2 = cache
        N = x.shape[0]

        # Output layer
        dW3 = h2.T @ grad                          # (64, 1)
        db3 = grad.sum(axis=0)                     # (1,)

        # Hidden 2 → output
        dh2 = grad @ self.W3.T                     # (N, 64)
        dz2 = dh2 * (z2 > 0)                       # ReLU backward
        dW2 = h1.T @ dz2                           # (64, 64)
        db2 = dz2.sum(axis=0)                      # (64,)

        # Hidden 1 → hidden 2
        dh1 = dz2 @ self.W2.T                      # (N, 64)
        dz1 = dh1 * (z1 > 0)                       # ReLU backward
        dW1 = x.T @ dz1                            # (input_dim, 64)
        db1 = dz1.sum(axis=0)                      # (64,)

        return {'W1': dW1, 'b1': db1, 'W2': dW2, 'b2': db2, 'W3': dW3, 'b3': db3}

    # ------------------------------------------------------------------
    # Adam optimizer
    # ------------------------------------------------------------------

    def _adam_update(self, grads: dict, lr: float):
        """Apply Adam update to all parameters in-place."""
        self._t += 1
        beta1, beta2 = 0.9, 0.999
        for name in ('W1', 'b1', 'W2', 'b2', 'W3', 'b3'):
            g = grads[name]
            state = self._adam[name]
            state['m'] = beta1 * state['m'] + (1 - beta1) * g
            state['v'] = beta2 * state['v'] + (1 - beta2) * (g ** 2)
            m_hat = state['m'] / (1 - beta1 ** self._t)
            v_hat = state['v'] / (1 - beta2 ** self._t)
            param = getattr(self, name)
            param -= lr * m_hat / (np.sqrt(v_hat) + 1e-8)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _scale_state(self, state: np.ndarray) -> np.ndarray:
        s = state.flatten() if hasattr(state, 'ndim') and state.ndim > 1 else np.asarray(state).flatten().copy()
        s[1] = s[1] / 50.0  # Normalize price to ~[0, 1]
        return s

    def _predict_q(self, params: dict, scaled_s: np.ndarray, action: float) -> float:
        """Q(s, a) for a single sample."""
        x = np.append(scaled_s, action).reshape(1, -1)
        q, _ = self._forward(x, params)
        return float(q[0, 0])

    def _max_q(self, params: dict, scaled_ns: np.ndarray, n_candidates: int = 10) -> float:
        """max_a Q(s', a) via discrete candidate sampling."""
        candidates = np.linspace(ACTION_MIN, ACTION_MAX, n_candidates)
        xs = np.column_stack([np.tile(scaled_ns, (n_candidates, 1)), candidates])
        qs, _ = self._forward(xs, params)
        return float(np.max(qs))

    def decay_epsilon(self):
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay

    def act(self, state: np.ndarray, train: bool = True) -> float:
        """Select action via epsilon-greedy or heuristic fallback."""
        s = state.flatten() if hasattr(state, 'ndim') and state.ndim > 1 else np.asarray(state).flatten()

        # Epsilon-greedy exploration
        if train and np.random.rand() <= self.epsilon:
            return np.random.uniform(ACTION_MIN, ACTION_MAX)

        # Heuristic fallback before network is trained
        if not self.is_fitted:
            occ = float(s[0])
            if occ > HIGH_OCCUPANCY_THRESHOLD:
                return AGENT_HIGH_ACTION
            if occ < LOW_OCCUPANCY_THRESHOLD:
                return AGENT_LOW_ACTION
            return AGENT_NEUTRAL_ACTION

        # Greedy action: batch-evaluate 10 candidate actions (whitepaper: "discretized into 10 intervals")
        scaled_s = self._scale_state(s)
        candidates = np.linspace(ACTION_MIN, ACTION_MAX, 10)
        xs = np.column_stack([np.tile(scaled_s, (10, 1)), candidates])
        qs, _ = self._forward(xs, self._params())
        return candidates[np.argmax(qs[:, 0])]

    def train(self, state: np.ndarray, action: float, reward: float,
              next_state: np.ndarray, done: bool):
        """Store experience, sample batch, and perform a DQN gradient step."""
        state = state.flatten() if hasattr(state, 'ndim') and state.ndim > 1 else np.asarray(state).flatten()
        next_state = next_state.flatten() if hasattr(next_state, 'ndim') and next_state.ndim > 1 else np.asarray(next_state).flatten()

        self.memory.append((state, action, reward, next_state, done))

        # Need minimum experiences before learning starts
        if len(self.memory) <= 64:
            return

        batch = random.sample(list(self.memory), min(len(self.memory), self.batch_size))

        X_list = []
        y_list = []

        for s, a, r, ns, d in batch:
            scaled_s = self._scale_state(s)
            scaled_ns = self._scale_state(ns)

            if d:
                target = r
            elif self.is_fitted:
                # Bootstrap from target network: r + γ · max_a' Q_target(s', a')
                target = r + self.gamma * self._max_q(self._params(target=True), scaled_ns)
            else:
                target = r

            X_list.append(np.append(scaled_s, a))
            y_list.append(target)

        X = np.array(X_list)                         # (batch, input_dim)
        y = np.array(y_list).reshape(-1, 1)          # (batch, 1)

        # Forward → MSE gradient → backward → Adam step
        pred, cache = self._forward(X, self._params())
        grad = pred - y                              # d(½(pred-y)²)/d_pred = pred - y
        grads = self._backward(grad, cache)
        self._adam_update(grads, self.lr)

        self.is_fitted = True
        self.update_counter += 1
        if self.update_counter % self.target_update_freq == 0:
            self._sync_target()

    # ------------------------------------------------------------------
    # Backward compatibility: agent.model.predict / agent.model.fit
    # ------------------------------------------------------------------

    @property
    def model(self) -> _ModelCompat:
        return _ModelCompat(self)

    @model.setter
    def model(self, _value):
        pass  # Ignore direct assignment (legacy MLPRegressor initialization paths)
