import logging
from typing import cast, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
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


@router.get("/zones", response_model=list[ZonePricingResponse])
async def get_zone_pricing(zone_id: Optional[str] = Query(None, description="Optional zone/lot ID to filter")):
    from src.api.database import get_db_cm, ParkingLot
    try:
        with get_db_cm() as db:
            lots = db.query(ParkingLot).all()
            if not lots:
                demo_prices = [
                    ("A1", 15.0, 50.0), ("L1", 25.0, 80.0), ("NY1", 35.0, 120.0),
                    ("SF1", 28.0, 90.0), ("TK1", 30.0, 100.0), ("DB1", 40.0, 150.0),
                    ("SG1", 22.0, 60.0), ("MB1", 12.0, 30.0), ("BR1", 18.0, 50.0),
                    ("M1", 14.0, 40.0),
                ]
                return [ZonePricingResponse(zone_id=z[0], base_price=z[1], price_range=[max(z[1] * 0.5, 1.0), z[2]], currency="USD", dynamic_pricing=True) for z in demo_prices]

            if zone_id:
                lot = next((l for l in lots if l.lot_id == zone_id), None)
                if not lot:
                    raise HTTPException(404, f"Zone {zone_id} not found")
                return [ZonePricingResponse(
                    zone_id=zone_id,
                    base_price=float(lot.base_price),
                    price_range=[max(float(lot.base_price) * 0.5, 1.0), float(lot.price_cap)],
                    currency="USD",
                    dynamic_pricing=True,
                )]

            return [ZonePricingResponse(
                zone_id=l.lot_id,
                base_price=float(l.base_price),
                price_range=[max(float(l.base_price) * 0.5, 1.0), float(l.price_cap)],
                currency="USD",
                dynamic_pricing=True,
            ) for l in lots]
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Zone pricing lookup failed for %s: %s", zone_id or "all", e)
        raise HTTPException(500, f"Zone pricing lookup failed: {e}")
