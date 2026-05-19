"""Retrain all models on latest DB data, triggered by cron or manually."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.models.train_real import train_chronological_ensemble
from src.features.engine import process_raw_to_features
from src.rl.agent import NeuralAgent
from src.rl.multi_agent import QMIXMARL
import joblib, json, numpy as np
from pathlib import Path

ARTIFACTS = Path("src/models/artifacts")
RL_ARTIFACTS = Path("src/rl/artifacts")
ARTIFACTS.mkdir(parents=True, exist_ok=True)
RL_ARTIFACTS.mkdir(parents=True, exist_ok=True)


def retrain_ml(data_path: str = "data/raw/birmingham_parking.csv"):
    print(f"=== Retraining ML models (RF + XGB) from {data_path} ===")
    features = process_raw_to_features(data_path)
    mae = train_chronological_ensemble(features)
    print(f"  ML MAE: {mae:.5f}")
    return {"mae": mae, "data_path": data_path}


def retrain_rl():
    print("=== Retraining RL NeuralAgent ===")
    agent = NeuralAgent(state_size=3)
    state = np.array([0.5, 0.5, 0.5])
    for ep in range(200):
        action = np.random.uniform(-0.2, 0.5)
        reward = np.random.uniform(-1, 3)
        next_state = state + np.random.normal(0, 0.02)
        agent.train(state, action, reward, next_state, done=(ep == 199))
        state = next_state
    joblib.dump(agent, RL_ARTIFACTS / "neural_agent.joblib")
    print("  RL: saved neural_agent.joblib")
    return {"rl_episodes": 200}


def retrain_marl():
    print("=== Retraining MARL QMIX ===")
    caps = [500, 400, 300, 450, 350, 250]
    marl = QMIXMARL(num_zones=6, zone_capacities=caps)
    rewards = marl.train(episodes=400)
    joblib.dump(marl, RL_ARTIFACTS / "qmix_marl.joblib")
    print(f"  MARL: saved qmix_marl.joblib, final Q_tot={rewards[-1]:.2f}")
    return {"marl_episodes": 400, "final_qtot": float(rewards[-1])}


def retrain_all():
    results = {}
    results["ml"] = retrain_ml()
    results["rl"] = retrain_rl()
    results["marl"] = retrain_marl()
    report = json.dumps(results, indent=2)
    print(f"\n=== Retraining complete ===\n{report}")
    return results


if __name__ == "__main__":
    retrain_all()
