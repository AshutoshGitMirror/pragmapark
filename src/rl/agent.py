import numpy as np
import random
import warnings
from copy import deepcopy
from collections import deque
from sklearn.neural_network import MLPRegressor
from sklearn.exceptions import ConvergenceWarning

warnings.filterwarnings("ignore", category=ConvergenceWarning)


class NeuralAgent:
    def __init__(self, state_size: int, action_size: int = 1):
        self.model = MLPRegressor(
            hidden_layer_sizes=(64, 64), activation='relu',
            solver='adam', learning_rate_init=0.001,
            warm_start=True, max_iter=10,
        )
        self.target_model = None
        self.target_update_counter = 0
        self.target_update_freq = 20
        self.epsilon = 1.0
        self.epsilon_decay = 0.98
        self.epsilon_min = 0.05
        self.gamma = 0.95
        self.memory: deque = deque(maxlen=2000)
        self.is_fitted = False

    def decay_epsilon(self):
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay

    def _scale_state(self, state):
        s = state.flatten() if state.ndim > 1 else state.copy()
        s[1] = s[1] / 50.0
        return s

    def _predict_q(self, model, scaled_s, action):
        inp = np.append(scaled_s, action).reshape(1, -1)
        return float(model.predict(inp)[0])

    def _max_q(self, model, scaled_ns, n_candidates: int = 10):
        candidates = np.linspace(-0.2, 0.5, n_candidates)
        return max(self._predict_q(model, scaled_ns, c) for c in candidates)

    def act(self, state, train=True):
        s = state.flatten() if hasattr(state, 'ndim') and state.ndim > 1 else np.asarray(state).flatten()
        if train and np.random.rand() <= self.epsilon:
            return np.random.uniform(-0.2, 0.5)
        if not self.is_fitted:
            occ = float(s[0])
            if occ > 0.8:
                return 0.2
            if occ < 0.4:
                return -0.1
            return 0.0
        scaled_s = self._scale_state(s)
        candidates = np.linspace(-0.2, 0.5, 30)
        return candidates[np.argmax([self._predict_q(self.model, scaled_s, c) for c in candidates])]

    def train(self, state, action, reward, next_state, done):
        state = state.flatten() if hasattr(state, 'ndim') and state.ndim > 1 else np.asarray(state).flatten()
        next_state = next_state.flatten() if hasattr(next_state, 'ndim') and next_state.ndim > 1 else np.asarray(next_state).flatten()
        self.memory.append((state, action, reward, next_state, done))
        if len(self.memory) <= 64:
            return
        model = self.target_model if self.target_model is not None else self.model
        batch = random.sample(list(self.memory), min(len(self.memory), 128))
        X, y = [], []
        for s, a, r, ns, d in batch:
            scaled_s = self._scale_state(s)
            scaled_ns = self._scale_state(ns)
            if d:
                target = r
            elif self.is_fitted:
                target = r + self.gamma * self._max_q(model, scaled_ns)
            else:
                target = r
            X.append(np.append(scaled_s, a))
            y.append(target)
        self.model.fit(np.array(X), np.array(y))
        self.is_fitted = True
        self.target_update_counter += 1
        if self.target_update_counter % self.target_update_freq == 0:
            self.target_model = deepcopy(self.model)
