import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from src.api.auth import get_current_user
from src.api.utils import require_admin
from src.pipeline.orchestrator import pipeline
from src.api.database import get_db_cm, ParkingLot, OccupancyRecord
from src.api.schemas import PricingRequest, PricingResponse, LotPricingResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/pricing", tags=["Pricing"])


@router.post("/adjust", response_model=PricingResponse)
def adjust_price(body: PricingRequest, user: dict = Depends(get_current_user)):
    require_admin(user)
    if not pipeline.pricing.agent_available:
        raise HTTPException(
            503, "RL Agent not trained. Run src/rl/train_control.py first."
        )

    new_price, multiplier = pipeline.pricing.get_price(
        occupancy=body.predicted_occupancy,
        current_price=body.current_price,
    )

    return PricingResponse(
        price_multiplier=round(float(multiplier), 4),
        new_price=round(float(new_price), 2),
        is_hike=bool(multiplier > 0),
    )


@router.get("/lots", response_model=list[LotPricingResponse])
def get_lot_pricing(
    lot_id: Optional[str] = Query(
        None, description="Optional lot ID to filter"
    ),
):
    try:
        with get_db_cm() as db:
            lots = db.query(ParkingLot).all()
            if not lots:
                demo_prices = [
                    ("A1", 15.0, 50.0),
                    ("L1", 25.0, 80.0),
                    ("NY1", 35.0, 120.0),
                    ("SF1", 28.0, 90.0),
                    ("TK1", 30.0, 100.0),
                    ("DB1", 40.0, 150.0),
                    ("SG1", 22.0, 60.0),
                    ("MB1", 12.0, 30.0),
                    ("BR1", 18.0, 50.0),
                    ("M1", 14.0, 40.0),
                ]
                return [
                    LotPricingResponse(
                        lot_id=z[0],
                        base_price=z[1],
                        price_range=[max(z[1] * 0.5, 1.0), z[2]],
                        currency="USD",
                        dynamic_pricing=True,
                    )
                    for z in demo_prices
                ]

            if lot_id:
                lot = next((lt for lt in lots if lt.lot_id == lot_id), None)
                if not lot:
                    raise HTTPException(404, f"Lot {lot_id} not found")
                return [
                    LotPricingResponse(
                        lot_id=lot_id,
                        base_price=float(lot.base_price),
                        price_range=[
                            max(float(lot.base_price) * 0.5, 1.0),
                            float(lot.price_cap),
                        ],
                        currency="USD",
                        dynamic_pricing=True,
                    )
                ]

            return [
                LotPricingResponse(
                    lot_id=lt.lot_id,
                    base_price=float(lt.base_price),
                    price_range=[
                        max(float(lt.base_price) * 0.5, 1.0),
                        float(lt.price_cap),
                    ],
                    currency="USD",
                    dynamic_pricing=True,
                )
                for lt in lots
            ]
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(
            "Lot pricing lookup failed for %s: %s", lot_id or "all", e
        )
        raise HTTPException(500, f"Lot pricing lookup failed: {e}")


@router.get("/history")
def get_pricing_history(days: int = Query(7, ge=1, le=30)):
    days_list = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    days_map = {
        0: "Mon",
        1: "Tue",
        2: "Wed",
        3: "Thu",
        4: "Fri",
        5: "Sat",
        6: "Sun",
    }

    grid = {}
    for day in days_list:
        for h in range(24):
            grid[(day, h)] = []

    try:
        with get_db_cm() as db:
            lots = db.query(ParkingLot).all()
            lot_base_prices = {lt.lot_id: float(lt.base_price) for lt in lots}

            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            records = (
                db.query(OccupancyRecord)
                .filter(OccupancyRecord.timestamp >= cutoff)
                .all()
            )

            for r in records:
                base_price = lot_base_prices.get(r.lot_id)
                if not base_price or base_price <= 0:
                    continue
                multiplier = float(r.price) / base_price

                day_idx = r.timestamp.weekday()
                day_name = days_map[day_idx]  # all 0-6 keys present
                hour = r.timestamp.hour

                if (day_name, hour) in grid:
                    grid[(day_name, hour)].append(multiplier)
    except Exception as e:
        logger.warning(
            "Failed to fetch real pricing history: %s. "
            "Using fallback pricing history.",
            e,
        )

    response_data = []
    avg_mult = 1.8

    for day_idx, day in enumerate(days_list):
        is_weekend = day_idx >= 5
        day_seed = day_idx * 0.03
        for h in range(24):
            multipliers = grid.get((day, h), [])
            if multipliers:
                val = sum(multipliers) / len(multipliers)
                val = max(0.5, min(5.0, val))
            else:
                hour_seed = h * 0.01
                if not is_weekend:
                    if h >= 8 and h <= 10:
                        base = avg_mult * 0.9 + 0.15 + (day_seed + hour_seed)
                    elif h >= 17 and h <= 19:
                        base = avg_mult * 1.1 + 0.1 + (day_seed + hour_seed)
                    elif h >= 11 and h <= 16:
                        base = avg_mult * 0.7 + 0.1 + (day_seed + hour_seed)
                    elif h >= 20 and h <= 22:
                        base = avg_mult * 0.5 + 0.08 + (day_seed + hour_seed)
                    else:
                        base = avg_mult * 0.3 + 0.05 + (day_seed + hour_seed)
                else:
                    if h >= 10 and h <= 16:
                        base = avg_mult * 0.6 + 0.1 + (day_seed + hour_seed)
                    elif h >= 17 and h <= 20:
                        base = avg_mult * 0.75 + 0.08 + (day_seed + hour_seed)
                    else:
                        base = avg_mult * 0.35 + 0.05 + (day_seed + hour_seed)
                val = base

            response_data.append(
                {"day": day, "hour": h, "multiplier": round(val, 2)}
            )

    return response_data
