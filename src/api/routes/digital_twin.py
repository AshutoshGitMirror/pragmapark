from fastapi import APIRouter, Depends
from src.api.database import get_session

router = APIRouter()

@router.get("/digital-twin/status")
def dt_status(db=Depends(get_session)):
    from src.pipeline.orchestrator import pipeline
    return pipeline.dt.summary()

@router.post("/digital-twin/scenario")
def dt_scenario(scenario_type: str = "zone_closure", zone_id: str = "zone_0"):
    from src.pipeline.orchestrator import pipeline
    return pipeline.run_digital_twin_scenario(scenario_type, zone_id)
