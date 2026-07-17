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
    TrainGeneratorRequest,
    ScenarioListItem,
    ScenarioRunResponse,
    GenerateScenarioResponse,
    TrainGeneratorResponse,
    ScenarioPipelineResponse,
)
from typing import List
import numpy as np

router = APIRouter(prefix="/api/v1/digital-twin", tags=["Digital Twin"])


_generative = pipeline.generator


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
        "generator_trained": _generative.trained,
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

                    occ_rate = float(latest.occupancy_rate) if latest else 0.5
                    price = (
                        float(latest.price)
                        if latest
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
        # Find and run a single named scenario
        matching = [
            s
            for s in pipeline.scenario_engine.scenarios
            if s.name == body.scenario_name
        ]
        if not matching:
            raise HTTPException(
                404, f"Scenario '{body.scenario_name}' not found"
            )
        # Run the specific scenario with VAE generation
        idx = pipeline.scenario_engine.scenarios.index(matching[0])
        v_occ, v_price, v_congestion, v_share = (
            pipeline.scenario_engine.generator.synthesize_scenario(
                base_state["occupancy_rate"],
                base_state["price"],
                scenario_idx=idx,
            )
        )
        v_state = {
            "occupancy_rate": v_occ,
            "price": v_price,
            "congestion": v_congestion,
            "resident_share": v_share,
        }
        modified = matching[0].run(base_state, v_state)
        result_item = {
            "scenario": matching[0].name,
            "description": matching[0].description,
            "impacts": matching[0].impacts,
            "result": modified,
        }
        occ_delta = matching[0].impacts.get("occupancy_rate_delta", 0)
        p_delta = matching[0].impacts.get("price_delta", 0)
        return ScenarioRunResponse(
            base_state=base_state,
            results=[result_item],
            comparisons=[
                {
                    "scenario": matching[0].name,
                    "occupancy_delta": f"{occ_delta:+.2%}",
                    "price_delta": f"₹{p_delta:+.2f}",
                    "congestion": modified.get("congestion_level", "unknown"),
                }
            ],
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
    if not _generative.trained:
        raise HTTPException(
            503, "Generative model not trained. Call /train first."
        )
    synthetic = _generative.synthesize_scenario(
        body.base_occupancy, body.base_price
    )
    return GenerateScenarioResponse(
        synthetic_occupancy=round(float(synthetic[0]), 4),
        synthetic_price=round(float(synthetic[1]), 2),
        congestion_score=round(float(synthetic[2]), 4),
        shared_occupancy=round(float(synthetic[3]), 4),
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


@router.post("/train-generator", response_model=TrainGeneratorResponse)
def train_generator(
    body: TrainGeneratorRequest, user: dict = Depends(get_current_user)
):
    require_admin(user)
    with get_db_cm() as db:
        samples = (
            db.query(
                OccupancyRecord.occupancy_rate,
                OccupancyRecord.price,
                OccupancyRecord.net_flux,
            )
            .order_by(OccupancyRecord.timestamp.desc())
            .limit(500)
            .all()
        )
        real_data = (
            np.array(
                [
                    [r.occupancy_rate, r.price / 50.0,
                     0.0 if r.occupancy_rate < 0.40
                     else 0.33 if r.occupancy_rate < 0.65
                     else 0.66 if r.occupancy_rate < 0.85
                     else 1.0,
                     0.5, 0.0]
                    for r in samples
                ]
            )
            if len(samples) >= 32
            else np.random.rand(100, 5) * 0.5 + 0.25
        )
    losses = _generative.train(real_data, epochs=min(body.epochs, 1000))
    return TrainGeneratorResponse(
        status="trained",
        epochs=body.epochs,
        final_loss=[losses[-1]] if losses else None,
    )
