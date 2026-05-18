import numpy as np
import joblib
import os
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/v1/pricing", tags=["Pricing"])

AGENT_DIR = "src/rl/artifacts"


def _load_agent():
    path = os.path.join(AGENT_DIR, "neural_agent.joblib")
    if not os.path.exists(path):
        return None
    return joblib.load(path)


@router.post("/adjust")
async def adjust_price(predicted_occupancy: float, current_price: float):
    agent = _load_agent()
    if agent is None:
        raise HTTPException(503, "RL Agent not trained. Run src/rl/train_control.py first.")

    state = np.array([predicted_occupancy, current_price, 0.5])
    multiplier = agent.act(state, train=False)
    new_price = float(np.clip(current_price * (1 + multiplier), 5, 50))

    return {
        "price_multiplier": round(multiplier, 4),
        "new_price": round(new_price, 2),
        "is_hike": multiplier > 0,
    }


@router.get("/zones")
async def get_zone_pricing(zone_id: str = "BHMBCCMKT01"):
    return {
        "zone_id": zone_id,
        "base_price": 10.0,
        "price_range": [5.0, 50.0],
        "currency": "USD",
        "dynamic_pricing": True,
    }
