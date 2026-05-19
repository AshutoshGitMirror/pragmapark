from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.digital_twin import ScenarioEngine, GenerativeSimulator
from src.pipeline.orchestrator import pipeline

router = APIRouter(prefix="/api/v1/digital-twin", tags=["Digital Twin"])


class ScenarioRequest(BaseModel):
    scenario_type: str = "zone_closure"
    zone_id: str = "zone_0"

_scenario_engine = ScenarioEngine()
_scenario_engine.register_defaults()
_generative = GenerativeSimulator(latent_dim=8)


@router.get("/scenarios")
async def list_scenarios():
    return [
        {"name": s.name, "description": s.description}
        for s in _scenario_engine.scenarios
    ]


@router.post("/scenarios/run")
async def run_scenarios(
    zone_id: str = "zone_0",
    occupancy_rate: float = 0.5,
    price: float = 10.0,
    total_slots: int = 500,
):
    base_state = {
        "zone_id": zone_id,
        "occupancy_rate": occupancy_rate,
        "price": price,
        "total_slots": total_slots,
        "available_slots": int(total_slots * (1 - occupancy_rate)),
        "congestion_level": "normal",
    }
    results = _scenario_engine.run_all(base_state)
    comparisons = _scenario_engine.compare(base_state)
    return {"base_state": base_state, "results": results, "comparisons": comparisons}


@router.post("/generate")
async def generate_scenario(base_occupancy: float = 0.5, base_price: float = 10.0):
    if not _generative.trained:
        raise HTTPException(503, "Generative model not trained. Call /train first.")
    synthetic = _generative.synthesize_scenario(base_occupancy, base_price)
    return {
        "synthetic_occupancy": round(float(synthetic[0]), 4),
        "synthetic_price": round(float(synthetic[1]), 2),
        "congestion_score": round(float(synthetic[2]), 4),
    }


@router.post("/scenario")
async def run_pipeline_scenario(req: ScenarioRequest):
    result = pipeline.run_digital_twin_scenario(
        scenario_type=req.scenario_type,
        zone_id=req.zone_id,
    )
    return result

@router.post("/train-generator")
async def train_generator(epochs: int = 200):
    real_data = np.random.rand(100, 4)
    losses = _generative.train(real_data, epochs=epochs)
    return {"status": "trained", "epochs": epochs, "final_losses": losses[-1] if losses else None}
