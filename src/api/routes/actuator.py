from fastapi import APIRouter, Depends
from src.pipeline.orchestrator import pipeline
from src.api.auth import get_current_user
from src.api.utils import require_admin

router = APIRouter(prefix="/api/v1/actuator", tags=["Actuator"])


@router.get("/status")
async def actuator_status(user: dict = Depends(get_current_user)):
    require_admin(user)
    return {
        "summary": pipeline.actuator.summary(),
        "zones": pipeline.actuator.zone_statuses(),
    }
