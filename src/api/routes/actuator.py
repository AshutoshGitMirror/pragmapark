from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from src.pipeline.orchestrator import pipeline
from src.api.auth import get_current_user
from src.api.utils import require_admin

router = APIRouter(prefix="/api/v1/actuator", tags=["Actuator"])


class ActuatorCommandRequest(BaseModel):
    zone_id: str
    command: str
    source: str = "api"


@router.get("/status")
async def actuator_status(user: dict = Depends(get_current_user)):
    require_admin(user)
    return {
        "summary": pipeline.actuator.summary(),
        "zones": pipeline.actuator.zone_statuses(),
    }


@router.post("/command")
async def actuator_command(
    req: ActuatorCommandRequest,
    user: dict = Depends(get_current_user),
):
    require_admin(user)
    bridge = pipeline.actuator

    if req.zone_id not in bridge.barriers:
        raise HTTPException(404, f"Zone '{req.zone_id}' not registered")

    if req.command == "toggle_barrier":
        barrier = bridge.barriers[req.zone_id]
        cmd = barrier.set_restricted(not barrier.restricted)
        bridge.command_log.append(cmd)
        return {"status": "ok", "command": req.command, "zone_id": req.zone_id, "open": not barrier.restricted}

    if req.command == "toggle_light":
        light = bridge.lights[req.zone_id]
        next_color = {"green": "yellow", "yellow": "red", "red": "green"}.get(light.color, "green")
        cmd = light.set_color(next_color)
        bridge.command_log.append(cmd)
        return {"status": "ok", "command": req.command, "zone_id": req.zone_id, "color": next_color}

    raise HTTPException(400, f"Unknown command '{req.command}'")
