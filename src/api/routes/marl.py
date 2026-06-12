import asyncio
from fastapi import APIRouter, Depends
from src.rl.multi_agent import QMIXMARL, ConnectedVehicle
import numpy as np
from src.api.auth import get_current_user
from src.api.utils import require_admin
from src.api.schemas import MARLRequest, MARLResponse, MARLStatusResponse

router = APIRouter(prefix="/api/v1/marl", tags=["Multi-Agent RL"])

_marl_instance = None


@router.post("/train", response_model=MARLResponse)
async def train_marl(
    body: MARLRequest, user: dict = Depends(get_current_user)
):
    require_admin(user)
    global _marl_instance
    capacities = [np.random.randint(200, 600) for _ in range(body.num_zones)]
    _marl_instance = QMIXMARL(body.num_zones, capacities)

    vehicles = [
        ConnectedVehicle(
            f"CV_{i}", np.random.randint(0, body.num_zones), "downtown"
        )
        for i in range(20)
    ]
    _marl_instance.register_vehicles(vehicles)

    rewards = await asyncio.to_thread(
        _marl_instance.train, episodes=body.episodes
    )
    validation = _marl_instance.validate()

    return MARLResponse(
        status="trained",
        num_zones=body.num_zones,
        episodes=body.episodes,
        final_reward=round(float(rewards[-1]), 2) if rewards else 0,
        validation=validation,
    )


@router.get("/status", response_model=MARLStatusResponse)
async def marl_status(user: dict = Depends(get_current_user)):
    require_admin(user)
    if _marl_instance is None:
        return MARLStatusResponse(status="not_trained")
    validation = _marl_instance.validate()
    return MARLStatusResponse(
        status="trained",
        num_zones=_marl_instance.num_zones,
        episodes_completed=len(_marl_instance.episode_rewards),
        mean_reward=round(float(np.mean(_marl_instance.episode_rewards)), 2),
        validation=validation,
    )
