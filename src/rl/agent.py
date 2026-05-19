import numpy as np
from collections import deque
import random


class NeuralAgent:
    def __init__(self, state_dim: int = 3, action_dim: int = 3, lr: float = 0.001):
        # weights-only neural net: state_dim -> 64 -> 64 -> action_dim
        self.w1 = np.random.randn(state_dim, 64).astype(np.float32) * 0.1
        self.b1 = np.zeros(64, dtype=np.float32)
        self.w2 = np.random.randn(64, 64).astype(np.float32) * 0.1
        self.b2 = np.zeros(64, dtype=np.float32)
        self.w3 = np.random.randn(64, action_dim).astype(np.float32) * 0.1
        self.b3 = np.zeros(action_dim, dtype=np.float32)
        self.lr = lr
        self.epsilon = 1.0
        self.gamma = 0.95
        self.memory = deque(maxlen=2000)
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.batch_size = 32
        self.train_step = 0
        self.target_update_freq = 20
        self._copy_to_target()

    def _copy_to_target(self):
        from copy import deepcopy
        self.target_w1 = deepcopy(self.w1)
        self.target_b1 = deepcopy(self.b1)
        self.target_w2 = deepcopy(self.w2)
        self.target_b2 = deepcopy(self.b2)
        self.target_w3 = deepcopy(self.w3)
        self.target_b3 = deepcopy(self.b3)

    def _forward(self, state: np.ndarray, w1, b1, w2, b2, w3, b3) -> np.ndarray:
        if state.ndim == 1:
            state = state.reshape(1, -1)
        h1 = np.maximum(state @ w1 + b1, 0)
        h2 = np.maximum(h1 @ w2 + b2, 0)
        return h2 @ w3 + b3

    def act(self, state: np.ndarray, train: bool = True) -> int:
        if state.ndim == 1:
            state = state.reshape(1, -1)
        if train and np.random.random() < self.epsilon:
            return int(np.random.randint(0, self.action_dim))
        q = self._forward(state, self.w1, self.b1, self.w2, self.b2, self.w3, self.b3)
        return int(np.argmax(q[0]))

    def remember(self, state, action, reward, next_state, done):
        self.memory.append((state, action, reward, next_state, done))

    def train(self):
        if len(self.memory) < self.batch_size:
            return None
        batch = random.sample(list(self.memory), self.batch_size)
        states = np.array([s for s, a, r, ns, d in batch], dtype=np.float32)
        actions = np.array([a for s, a, r, ns, d in batch], dtype=np.int64)
        rewards = np.array([r for s, a, r, ns, d in batch], dtype=np.float32)
        next_states = np.array([ns for s, a, r, ns, d in batch], dtype=np.float32)
        dones = np.array([d for s, a, r, ns, d in batch], dtype=np.float32)

        if states.ndim == 2:
            states = states.reshape(states.shape[0], -1)
        if next_states.ndim == 2:
            next_states = next_states.reshape(next_states.shape[0], -1)

        if states.shape[1] != self.state_dim:
            return None

        q_target_next = self._forward(
            next_states, self.target_w1, self.target_b1,
            self.target_w2, self.target_b2,
            self.target_w3, self.target_b3
        )
        max_q = np.max(q_target_next, axis=1)
        targets = rewards + self.gamma * max_q * (1 - dones)

        q_current = self._forward(
            states, self.w1, self.b1, self.w2, self.b2, self.w3, self.b3
        )
        dq = np.zeros_like(q_current)
        for i in range(self.batch_size):
            dq[i, actions[i]] = q_current[i, actions[i]] - targets[i]

        h1 = np.maximum(states @ self.w1 + self.b1, 0)
        h2 = np.maximum(h1 @ self.w2 + self.b2, 0)
        dh3 = dq
        dw3 = h2.T @ dh3 / self.batch_size
        db3 = np.mean(dh3, axis=0)
        dh2 = (dh3 @ self.w3.T) * (h2 > 0)
        dw2 = h1.T @ dh2 / self.batch_size
        db2 = np.mean(dh2, axis=0)
        dh1 = (dh2 @ self.w2.T) * (h1 > 0)
        dw1 = states.T @ dh1 / self.batch_size
        db1 = np.mean(dh1, axis=0)

        self.w3 -= self.lr * dw3
        self.b3 -= self.lr * db3
        self.w2 -= self.lr * dw2
        self.b2 -= self.lr * db2
        self.w1 -= self.lr * dw1
        self.b1 -= self.lr * db1

        self.train_step += 1
        if self.train_step % self.target_update_freq == 0:
            self._copy_to_target()

        return float(np.mean(np.abs(dq)))

    def decay_epsilon(self, factor: float = 0.995, min_eps: float = 0.01):
        self.epsilon = max(min_eps, self.epsilon * factor)
