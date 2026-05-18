from fastapi import APIRouter
from src.rl.multi_agent import QMIXMARL, ConnectedVehicle
import numpy as np

router = APIRouter(prefix="/api/v1/marl", tags=["Multi-Agent RL"])

_marl_instance = None


@router.post("/train")
async def train_marl(num_zones: int = 4, episodes: int = 200):
    global _marl_instance
    capacities = [np.random.randint(200, 600) for _ in range(num_zones)]
    _marl_instance = QMIXMARL(num_zones, capacities)

    vehicles = [
        ConnectedVehicle(f"CV_{i}", np.random.randint(0, num_zones), "downtown")
        for i in range(20)
    ]
    _marl_instance.register_vehicles(vehicles)

    rewards = _marl_instance.train(episodes=episodes)
    validation = _marl_instance.validate()

    return {
        "status": "trained",
        "num_zones": num_zones,
        "episodes": episodes,
        "final_reward": round(float(rewards[-1]), 2) if rewards else 0,
        "validation": validation,
    }


@router.get("/status")
async def marl_status():
    if _marl_instance is None:
        return {"status": "not_trained"}
    validation = _marl_instance.validate()
    return {
        "status": "trained",
        "num_zones": _marl_instance.num_zones,
        "episodes_completed": len(_marl_instance.episode_rewards),
        "mean_reward": round(float(np.mean(_marl_instance.episode_rewards)), 2),
        "validation": validation,
    }
