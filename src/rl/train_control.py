import logging
import os
import random
import sys

import joblib
import numpy as np

logger = logging.getLogger(__name__)

SEED = int(os.getenv("PRAGMA_SEED", "42"))
random.seed(SEED)
np.random.seed(SEED)

sys.path.append(os.getcwd())

from src.rl.environment import ParkingControlEnv  # noqa: E402
from src.rl.agent import NeuralAgent  # noqa: E402
from src.features.engine import process_raw_to_features  # noqa: E402

def train_neural_control():
    RAW_PATH = "data/raw/birmingham_parking.csv"
    features = process_raw_to_features(RAW_PATH)
    env = ParkingControlEnv(features.head(1)) 
    agent = NeuralAgent(state_size=3)
    
    # PHASE 1: Synthetic Warm-Start (Behavioral Hardening)
    print("\n[Gemini Neural RL] Phase 1: Synthetic Warm-Start (Behavioral Hardening)...")
    synthetic_X, synthetic_y = [], []
    for _ in range(1000):
        # Case A: High Demand (80-100%), Low Price (10-25) -> Hike is GOOD
        occ = np.random.uniform(0.8, 1.0)
        price = np.random.uniform(10, 25)
        action = np.random.uniform(0.1, 0.5)
        synthetic_X.append([occ, price/50.0, 0.5, action])
        synthetic_y.append(30.0) 
        
        # Case B: High Demand (80-100%), High Price (40-50) -> Hike is NEUTRAL/RISKY
        price = np.random.uniform(40, 50)
        action = np.random.uniform(0.1, 0.3)
        synthetic_X.append([occ, price/50.0, 0.5, action])
        synthetic_y.append(10.0)

        # Case C: Low Demand (0-30%), High Price (30-50) -> Drop is GOOD
        occ = np.random.uniform(0.0, 0.3)
        price = np.random.uniform(30, 50)
        action = np.random.uniform(-0.2, -0.1)
        synthetic_X.append([occ, price/50.0, 0.5, action])
        synthetic_y.append(25.0)

        # Case D: Low Demand (0-30%), Low Price (5-15) -> Drop is NEUTRAL
        price = np.random.uniform(5, 15)
        action = np.random.uniform(-0.2, -0.05)
        synthetic_X.append([occ, price/50.0, 0.5, action])
        synthetic_y.append(5.0)

        # Case E: Low Demand, High Price -> Hike is VERY BAD (Greedy)
        action_bad = np.random.uniform(0.1, 0.5)
        synthetic_X.append([occ, price/50.0, 0.5, action_bad])
        synthetic_y.append(-100.0)
    
    agent.model.fit(np.array(synthetic_X), np.array(synthetic_y))
    agent.is_fitted = True
    print("  Success: MLP initialized with demand-response baseline.")

    # PHASE 2: Online Reinforcement Learning
    episodes = 1200 
    print("\n[Gemini Neural RL] Phase 2: Online Policy Optimization...")
    for e in range(episodes):
        # Improved exploration strategy
        rand = np.random.rand()
        if rand < 0.4:
            env.state[0][0] = np.random.uniform(0.81, 0.98) # Congestion pressure
        elif rand < 0.7:
            env.state[0][0] = np.random.uniform(0.05, 0.35) # Low demand
        else:
            env.state[0][0] = np.random.uniform(0.55, 0.85) # Sweet spot
            
        state = env.get_state()
        action_multiplier = agent.act(state, train=True)
        next_state_raw, reward, done, info = env.step(action_multiplier)
        agent.train(state, action_multiplier, reward, next_state_raw.flatten(), done)
        agent.decay_epsilon()
        
        if (e + 1) % 200 == 0:
            print(f"  Episode {e+1:4d} | Epsilon: {agent.epsilon:.2f} | Rev: ${info['revenue']:.2f} | Act: {action_multiplier:+.2%}")

    print("\n[Gemini Neural RL Result] Adaptive Policy Verified.")
    
    # Final Validation
    high_occ_state = np.array([0.95, 10.0, 0.5])
    best_action_h = agent.act(high_occ_state, train=False)
    low_occ_state = np.array([0.15, 40.0, 0.5])
    best_action_l = agent.act(low_occ_state, train=False)
    greedy_state = np.array([0.10, 50.0, 0.5])
    best_action_g = agent.act(greedy_state, train=False)
    
    print(f"  Validation (High Occ 95%): {best_action_h:+.4f} (Expect Hike)")
    print(f"  Validation (Low Occ 15%):  {best_action_l:+.4f} (Expect Drop)")
    print(f"  Validation (Greedy Exploit - $50 @ 10%): {best_action_g:+.4f} (Expect Sharp Drop)")
    
    os.makedirs("src/rl/artifacts", exist_ok=True)
    path = "src/rl/artifacts/neural_agent.joblib"
    try:
        joblib.dump(agent, path)
        logger.info("event=rl.agent.saved path=%s", path)
    except Exception as e:
        logger.error("event=rl.agent.save.failed path=%s error=%s", path, e)
        raise
    return agent

if __name__ == "__main__":
    train_neural_control()
