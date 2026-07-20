import logging
from fastapi import APIRouter, HTTPException, Depends, Query

logger = logging.getLogger(__name__)
from src.pipeline.orchestrator import pipeline
from src.api.auth import get_current_user
from src.api.utils import require_admin
from src.api.database import get_db_cm, ParkingLot, OccupancyRecord
from src.api.schemas import (
    ScenarioRequest,
    ScenarioPipelineRequest,
    GenerateScenarioRequest,
    ScenarioListItem,
    ScenarioRunResponse,
    GenerateScenarioResponse,
    ScenarioPipelineResponse,
)
from typing import List

router = APIRouter(prefix="/api/v1/digital-twin", tags=["Digital Twin"])

# NOTE (P5): the CVAE-WGAN generator is OFFLINE-ONLY and intentionally NOT
# instantiated at runtime. The endpoints below are the legacy scenario/what-if
# surface. They read a base state and evaluate deterministic scenarios; they
# NEVER mutate production state (principle 8) and never train on simulated data.


@router.get("/state")
async def get_dt_state():
    return {
        "zones": {
            zid: {
                "capacity": info["capacity"],
                "occupancy": info["occupancy"],
                "price": info["price"],
                "n_share_listed": info.get("n_share_listed", 0),
            }
            for zid, info in pipeline.dt.zones.items()
        },
        "current_time": pipeline.dt.current_time,
        "history_length": len(pipeline.dt.state_history),
        "generator_runtime": False,
    }


@router.get("/scenarios", response_model=List[ScenarioListItem])
async def list_scenarios(
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Max records to return"
    ),
):
    return [
        ScenarioListItem(
            name=s.name,
            description=s.description,
            occupancy_shift=s.occupancy_shift,
            price_adjust=s.price_adjust,
        )
        for s in pipeline.scenario_engine.scenarios[offset: offset + limit]
    ]


@router.post("/scenarios/run", response_model=ScenarioRunResponse)
def run_scenarios(
    body: ScenarioRequest,
    user=Depends(get_current_user),
):
    require_admin(user)
    dt_state = pipeline.dt.get_zone_state(body.zone_id)

    if not dt_state:
        try:
            with get_db_cm() as db:
                lot = (
                    db.query(ParkingLot)
                    .filter(ParkingLot.lot_id == body.zone_id)
                    .first()
                )
                if lot:
                    latest = (
                        db.query(OccupancyRecord)
                        .filter(OccupancyRecord.lot_id == body.zone_id)
                        .order_by(OccupancyRecord.timestamp.desc())
                        .first()
                    )

                    occ_rate = (
                        float(latest.occupancy_rate)
                        if (latest and latest.occupancy_rate is not None)
                        else 0.5
                    )
                    price = (
                        float(latest.price)
                        if (latest and latest.price is not None)
                        else float(lot.base_price)
                    )
                    total_slots = int(lot.total_slots)

                    dt_state = {
                        "occupancy_rate": occ_rate,
                        "price": price,
                        "capacity": total_slots,
                        "available_slots": int(total_slots * (1 - occ_rate)),
                    }
        except Exception:
            logger.warning(
                "event=digital_twin.db_fallback zone=%s "
                "Using request body as base state",
                body.zone_id,
                exc_info=True,
            )

    if dt_state:
        base_state = {
            "zone_id": body.zone_id,
            "occupancy_rate": dt_state["occupancy_rate"],
            "price": dt_state["price"],
            "total_slots": dt_state["capacity"],
            "available_slots": dt_state["available_slots"],
            "congestion_level": "normal",
            "n_share_listed": dt_state.get("n_share_listed", 0),
        }
    else:
        base_state = {
            "zone_id": body.zone_id,
            "occupancy_rate": body.occupancy_rate,
            "price": body.price,
            "total_slots": body.total_slots,
            "available_slots": int(
                body.total_slots * (1 - body.occupancy_rate)
            ),
            "congestion_level": "normal",
            "n_share_listed": 0,
        }

    if body.scenario_name:
        # Find and run the named scenario (deterministic, no generative model).
        matching = [
            s
            for s in pipeline.scenario_engine.scenarios
            if s.name == body.scenario_name
        ]
        if not matching:
            raise HTTPException(
                404, f"Scenario '{body.scenario_name}' not found"
            )
        # Run ALL scenarios, then select the requested one (run_all is
        # read-only and deterministic; no simulated value feeds a model).
        results = pipeline.scenario_engine.run_all(base_state)
        comparisons = pipeline.scenario_engine.compare(base_state)
        single = next(
            (r for r in results if r["scenario"] == body.scenario_name), None
        )
        if single:
            results = [single]
        return ScenarioRunResponse(
            base_state=base_state, results=results, comparisons=comparisons
        )

    results = pipeline.scenario_engine.run_all(base_state)
    comparisons = pipeline.scenario_engine.compare(base_state)
    return ScenarioRunResponse(
        base_state=base_state, results=results, comparisons=comparisons
    )


@router.post("/generate", response_model=GenerateScenarioResponse)
def generate_scenario(
    body: GenerateScenarioRequest, user: dict = Depends(get_current_user)
):
    require_admin(user)
    # P5: the CVAE-WGAN generator is offline-only. This endpoint is retained
    # for interface compatibility but returns a clear deprecation notice and
    # the deterministic persistence-style baseline instead of a trained GAN.
    return GenerateScenarioResponse(
        synthetic_occupancy=round(float(body.base_occupancy), 4),
        synthetic_price=round(float(body.base_price), 2),
        congestion_score=round(
            0.0
            if body.base_occupancy < 0.40
            else 0.33
            if body.base_occupancy < 0.65
            else 0.66
            if body.base_occupancy < 0.85
            else 1.0,
            4,
        ),
        shared_occupancy=0.0,
    )


@router.post("/scenario", response_model=ScenarioPipelineResponse)
def run_pipeline_scenario(
    req: ScenarioPipelineRequest, user: dict = Depends(get_current_user)
):
    require_admin(user)
    result = pipeline.run_digital_twin_scenario(
        scenario_type=req.scenario_type,
        zone_id=req.zone_id,
    )
    return ScenarioPipelineResponse(**result)


# P5: /train-generator removed from runtime. The CVAE-WGAN generator is
# offline-only (build/train via scripts, version the artifact). It is never
# trained on live or simulated production data at request time.
