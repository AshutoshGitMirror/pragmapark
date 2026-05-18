import numpy as np
import random
import warnings
from sklearn.neural_network import MLPRegressor
from sklearn.exceptions import ConvergenceWarning

# Suppress annoying convergence warnings for the CLI output
warnings.filterwarnings("ignore", category=ConvergenceWarning)

class NeuralAgent:
    def __init__(self, state_size, action_size=1):
        # Optimized MLP for stable Reinforcement Learning
        self.model = MLPRegressor(
            hidden_layer_sizes=(64, 64), # More depth
            activation='relu',
            solver='adam',
            learning_rate_init=0.001, # Lower learning rate for RL stability
            warm_start=True,
            max_iter=50 # Better convergence per fit
        )
        self.epsilon = 1.0
        self.epsilon_decay = 0.995 # Slower decay for better exploration
        self.epsilon_min = 0.05
        self.gamma = 0.95 # Higher gamma for long-term utility
        self.memory = []
        self.is_fitted = False

    def _scale_state(self, state):
        # Scale price (index 1) from [5, 50] to [0.1, 1.0]
        scaled = state.copy()
        scaled[1] = scaled[1] / 50.0
        return scaled

    def act(self, state, train=True):
        if train and np.random.rand() <= self.epsilon:
            return np.random.uniform(-0.2, 0.5)
        
        if not self.is_fitted:
            occ = state[0]
            if occ > 0.8: return 0.2
            if occ < 0.4: return -0.1
            return 0.0
            
        scaled_s = self._scale_state(state)
        # Sample candidates to find the max-Q action
        candidates = np.linspace(-0.2, 0.5, 30) # More candidates
        q_values = []
        for c in candidates:
            inp = np.append(scaled_s, c).reshape(1, -1)
            q_values.append(self.model.predict(inp)[0])
        
        return candidates[np.argmax(q_values)]

    def train(self, state, action, reward, next_state, done):
        self.memory.append((state, action, reward, next_state, done))
        if len(self.memory) > 2000:
            self.memory.pop(0)
            
        if len(self.memory) > 64:
            batch = random.sample(self.memory, min(len(self.memory), 128))
            X, y = [], []
            
            for s, a, r, ns, d in batch:
                scaled_s = self._scale_state(s)
                scaled_ns = self._scale_state(ns)
                
                if d:
                    target = r
                else:
                    if self.is_fitted:
                        next_candidates = np.linspace(-0.2, 0.5, 10) # Better max-Q estimation
                        next_qs = [self.model.predict(np.append(scaled_ns, nc).reshape(1, -1))[0] for nc in next_candidates]
                        target = r + self.gamma * np.max(next_qs)
                    else:
                        target = r
                X.append(np.append(scaled_s, a))
                y.append(target)
            
            self.model.fit(np.array(X), np.array(y))
            self.is_fitted = True
            if self.epsilon > self.epsilon_min:
                self.epsilon *= self.epsilon_decay
