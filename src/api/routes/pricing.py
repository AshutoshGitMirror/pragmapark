import numpy as np
import joblib
import os
import logging
from fastapi import APIRouter, HTTPException, Depends
from src.api.auth import get_current_user
from src.api.schemas import PricingRequest, PricingResponse, ZonePricingResponse
from src.constants import PRICE_MIN, PRICE_MAX

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/pricing", tags=["Pricing"])

AGENT_DIR = os.getenv("PRICING_AGENT_DIR", "src/rl/artifacts")


def _load_agent():
    path = os.path.join(AGENT_DIR, "neural_agent.joblib")
    if not os.path.exists(path):
        return None
    try:
        return joblib.load(path)
    except Exception:
        return None


@router.post("/adjust", response_model=PricingResponse)
async def adjust_price(body: PricingRequest, user: dict = Depends(get_current_user)):
    agent = _load_agent()
    if agent is None:
        raise HTTPException(503, "RL Agent not trained. Run src/rl/train_control.py first.")

    state = np.array([body.predicted_occupancy, body.current_price, 0.5])
    multiplier = agent.act(state, train=False)
    new_price = float(np.clip(body.current_price * (1 + multiplier), PRICE_MIN, PRICE_MAX))

    return PricingResponse(
        price_multiplier=round(float(multiplier), 4),
        new_price=round(float(new_price), 2),
        is_hike=bool(multiplier > 0),
    )


@router.get("/zones", response_model=ZonePricingResponse)
async def get_zone_pricing(zone_id: str = "BHMBCCMKT01", user: dict = Depends(get_current_user)):
    from src.api.database import get_session, ParkingLot, OccupancyRecord
    from sqlalchemy import func
    db = get_session()
    try:
        lot = db.query(ParkingLot).filter(ParkingLot.lot_id == zone_id).first()
        if lot:
            latest = db.query(OccupancyRecord).filter(
                OccupancyRecord.lot_id == zone_id
            ).order_by(OccupancyRecord.timestamp.desc()).first()
            base_price = float(lot.base_price)
            price_cap = float(lot.price_cap)
            current_price = float(latest.price) if latest else base_price
            return ZonePricingResponse(
                zone_id=zone_id,
                base_price=base_price,
                price_range=[min(base_price * 0.5, 1.0), price_cap],
                currency="USD",
                dynamic_pricing=True,
            )
    except Exception as e:
        logger.warning("Zone pricing lookup failed for %s: %s", zone_id, e)
    finally:
        db.close()
    return ZonePricingResponse(
        zone_id=zone_id,
        base_price=10.0,
        price_range=[5.0, 50.0],
        currency="USD",
        dynamic_pricing=True,
    )
