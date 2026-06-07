from fastapi import APIRouter, HTTPException, Depends, Query
from src.pipeline.orchestrator import pipeline
from src.api.auth import get_current_user
from src.api.utils import require_admin
from src.api.schemas import ScenarioRequest, ScenarioPipelineRequest, GenerateScenarioRequest, TrainGeneratorRequest, ScenarioListItem, ScenarioRunResponse, GenerateScenarioResponse, TrainGeneratorResponse, ScenarioPipelineResponse
from typing import List
import numpy as np

router = APIRouter(prefix="/api/v1/digital-twin", tags=["Digital Twin"])


_generative = pipeline.generator


@router.get("/scenarios", response_model=List[ScenarioListItem])
async def list_scenarios(offset: int = Query(0, ge=0, description="Number of records to skip"),
                         limit: int = Query(100, ge=1, le=1000, description="Max records to return")):
    return [
        ScenarioListItem(name=s.name, description=s.description)
        for s in pipeline.scenario_engine.scenarios[offset:offset + limit]
    ]


@router.post("/scenarios/run", response_model=ScenarioRunResponse)
async def run_scenarios(
    body: ScenarioRequest,
    user=Depends(get_current_user),
):
    dt_state = pipeline.dt.get_zone_state(body.zone_id)

    if dt_state:
        base_state = {
            "zone_id": body.zone_id,
            "occupancy_rate": dt_state["occupancy_rate"],
            "price": dt_state["price"],
            "total_slots": dt_state["capacity"],
            "available_slots": dt_state["available_slots"],
            "congestion_level": "normal",
        }
    else:
        base_state = {
            "zone_id": body.zone_id,
            "occupancy_rate": body.occupancy_rate,
            "price": body.price,
            "total_slots": body.total_slots,
            "available_slots": int(body.total_slots * (1 - body.occupancy_rate)),
            "congestion_level": "normal",
        }

    if body.scenario_name:
        # Find and run a single named scenario
        matching = [s for s in pipeline.scenario_engine.scenarios if s.name == body.scenario_name]
        if not matching:
            raise HTTPException(404, f"Scenario '{body.scenario_name}' not found")
        # Run the specific scenario with VAE generation
        idx = pipeline.scenario_engine.scenarios.index(matching[0])
        v_occ, v_price, v_congestion = pipeline.scenario_engine.generator.synthesize_scenario(
            base_state["occupancy_rate"], base_state["price"], scenario_idx=idx)
        v_state = {"occupancy_rate": v_occ, "price": v_price, "congestion": v_congestion}
        modified = matching[0].run(base_state, v_state)
        result_item = {
            "scenario": matching[0].name,
            "description": matching[0].description,
            "impacts": matching[0].impacts,
            "result": modified,
        }
        return ScenarioRunResponse(
            base_state=base_state,
            results=[result_item],
            comparisons=[{
                "scenario": matching[0].name,
                "occupancy_delta": f"{matching[0].impacts.get('occupancy_rate_delta', 0):+.2%}",
                "price_delta": f"${matching[0].impacts.get('price_delta', 0):+.2f}",
                "congestion": modified.get("congestion_level", "unknown"),
            }],
        )

    results = pipeline.scenario_engine.run_all(base_state)
    comparisons = pipeline.scenario_engine.compare(base_state)
    return ScenarioRunResponse(base_state=base_state, results=results, comparisons=comparisons)


@router.post("/generate", response_model=GenerateScenarioResponse)
async def generate_scenario(body: GenerateScenarioRequest, user: dict = Depends(get_current_user)):
    require_admin(user)
    if not _generative.trained:
        raise HTTPException(503, "Generative model not trained. Call /train first.")
    synthetic = _generative.synthesize_scenario(body.base_occupancy, body.base_price)
    return GenerateScenarioResponse(
        synthetic_occupancy=round(float(synthetic[0]), 4),
        synthetic_price=round(float(synthetic[1]), 2),
        congestion_score=round(float(synthetic[2]), 4),
    )


@router.post("/scenario", response_model=ScenarioPipelineResponse)
async def run_pipeline_scenario(req: ScenarioPipelineRequest, user: dict = Depends(get_current_user)):
    result = pipeline.run_digital_twin_scenario(
        scenario_type=req.scenario_type,
        zone_id=req.zone_id,
    )
    return ScenarioPipelineResponse(**result)

@router.post("/train-generator", response_model=TrainGeneratorResponse)
async def train_generator(body: TrainGeneratorRequest, user: dict = Depends(get_current_user)):
    require_admin(user)
    from src.api.database import get_db_cm, OccupancyRecord
    with get_db_cm() as db:
        samples = db.query(OccupancyRecord.occupancy_rate, OccupancyRecord.price, OccupancyRecord.net_flux).order_by(OccupancyRecord.timestamp.desc()).limit(500).all()
        real_data = np.array([[r.occupancy_rate, r.price / 50.0, r.net_flux, 0.5] for r in samples]) if len(samples) >= 32 else np.random.rand(100, 4) * 0.5 + 0.25
    losses = _generative.train(real_data, epochs=min(body.epochs, 1000))
    return TrainGeneratorResponse(
        status="trained", epochs=body.epochs,
        final_loss=[losses[-1]] if losses else None,
    )
