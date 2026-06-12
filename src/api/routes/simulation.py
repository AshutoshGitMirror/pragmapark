from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
import logging

from src.api.auth import get_current_user
from src.api.utils import require_admin
from src.simulation.time_machine import time_machine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/simulation", tags=["simulation"])


class SpeedRequest(BaseModel):
    speedup: int = Field(ge=1, le=86400)


class SimulationStatusResponse(BaseModel):
    speedup: int
    is_fast_forwarding: bool
    real_time: str
    snapshot_exists: bool


class ResetResponse(BaseModel):
    success: bool
    message: str


class SnapshotResponse(BaseModel):
    success: bool
    message: str


@router.get("/status", response_model=SimulationStatusResponse)
async def simulation_status(user: dict = Depends(get_current_user)):
    tm = time_machine
    snap_exists = (
        tm._snapshot_path is not None and tm._snapshot_path.exists()
        if tm._snapshot_path
        else False
    )
    return SimulationStatusResponse(
        speedup=tm.speedup,
        is_fast_forwarding=tm.is_fast_forwarding,
        real_time=tm.get_sim_time().isoformat(),
        snapshot_exists=snap_exists,
    )


@router.post("/speed")
async def set_speed(req: SpeedRequest, user: dict = Depends(get_current_user)):
    require_admin(user)
    ok = time_machine.set_speedup(req.speedup)
    if not ok:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to create snapshot"
        )
    try:
        from src.api.server import _restart_background_tasks

        _restart_background_tasks()
    except ImportError:
        pass
    return {
        "speedup": time_machine.speedup,
        "is_fast_forwarding": time_machine.is_fast_forwarding,
    }


@router.post("/reset", response_model=ResetResponse)
async def reset_simulation(user: dict = Depends(get_current_user)):
    require_admin(user)
    ok = time_machine.reset_to_real()
    if not ok:
        return ResetResponse(
            success=False, message="No snapshot available or restore failed"
        )
    try:
        from src.api.server import _restart_background_tasks

        _restart_background_tasks()
    except ImportError:
        pass
    return ResetResponse(
        success=True,
        message="Database restored from snapshot. Clock reset to real time.",
    )


@router.post("/snapshot", response_model=SnapshotResponse)
async def take_snapshot(user: dict = Depends(get_current_user)):
    require_admin(user)
    ok = time_machine._take_snapshot()
    if not ok:
        return SnapshotResponse(success=False, message="Snapshot failed")
    return SnapshotResponse(success=True, message="Snapshot saved")
