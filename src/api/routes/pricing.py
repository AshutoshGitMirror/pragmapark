import logging
from typing import cast
from fastapi import APIRouter, HTTPException, Depends
from src.api.auth import get_current_user, get_optional_user
from src.api.schemas import PricingRequest, PricingResponse, ZonePricingResponse
from src.pipeline.orchestrator import pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/pricing", tags=["Pricing"])


@router.post("/adjust", response_model=PricingResponse)
async def adjust_price(body: PricingRequest, user: dict = Depends(get_current_user)):
    if not pipeline.pricing.agent_available:
        raise HTTPException(503, "RL Agent not trained. Run src/rl/train_control.py first.")

    new_price, multiplier = pipeline.pricing.get_price(
        occupancy=body.predicted_occupancy,
        current_price=body.current_price,
    )

    return PricingResponse(
        price_multiplier=round(float(multiplier), 4),
        new_price=round(float(new_price), 2),
        is_hike=bool(multiplier > 0),
    )


@router.get("/zones", response_model=ZonePricingResponse)
async def get_zone_pricing(zone_id: str = "BHMBCCMKT01"):
    from src.api.database import get_db_cm, ParkingLot
    try:
        with get_db_cm() as db:
            lot = db.query(ParkingLot).filter(ParkingLot.lot_id == zone_id).first()
            if not lot:
                raise HTTPException(404, f"Zone {zone_id} not found")
            from decimal import Decimal
            base_price = float(cast(Decimal, lot.base_price))
            price_cap = float(cast(Decimal, lot.price_cap))

            return ZonePricingResponse(
                zone_id=zone_id,
                base_price=base_price,
                price_range=[min(base_price * 0.5, 1.0), price_cap],
                currency="USD",
                dynamic_pricing=True,
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Zone pricing lookup failed for %s: %s", zone_id, e)
        raise HTTPException(500, f"Zone pricing lookup failed: {e}")
