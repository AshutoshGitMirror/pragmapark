"""Sensor management API.

Lot owners (and admins) create and manage per-device API keys for their
lots. Each sensor is bound to exactly one lot and inherits that lot's
ownership, so a key can only push data for its own lot. Admins may list
and operate on every sensor (fleet-wide visibility).
"""

import logging
import secrets
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from src.api.auth import get_current_user
from src.api.database import ParkingLot, Sensor, User, get_db
from src.api.schemas import (
    SensorCreateRequest,
    SensorCreateResponse,
    SensorResponse,
    SensorRotateResponse,
    SensorUpdateRequest,
)
from src.api.sensor_auth import generate_sensor_key, hash_sensor_key
from src.api.utils import require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/sensors", tags=["Sensors"])


def _get_lot_or_404(lot_id: str, db):
    lot = db.query(ParkingLot).filter(ParkingLot.lot_id == lot_id).first()
    if not lot:
        raise HTTPException(404, f"Lot {lot_id} not found")
    return lot


def _assert_owner_or_admin(user: dict, lot: ParkingLot, db):
    """Allow admins; otherwise require the caller to own the lot."""
    if user.get("role") == "admin":
        return
    caller = db.query(User).filter(User.email == user.get("sub")).first()
    if not caller or not lot.owner_id or lot.owner_id != caller.id:
        raise HTTPException(403, "You do not own this lot")


def _to_response(sensor: Sensor) -> SensorResponse:
    return SensorResponse(
        sensor_id=sensor.sensor_id,
        lot_id=sensor.lot_id,
        label=sensor.label,
        owner_id=sensor.owner_id,
        active=sensor.active,
        created_at=sensor.created_at,
        last_used_at=sensor.last_used_at,
    )


@router.post("", response_model=SensorCreateResponse, status_code=201)
async def create_sensor(
    req: SensorCreateRequest,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    require_role(user, {"admin", "lot_owner"})
    lot = _get_lot_or_404(req.lot_id, db)
    _assert_owner_or_admin(user, lot, db)
    api_key = generate_sensor_key()
    sensor = Sensor(
        sensor_id="sensor_" + secrets.token_hex(8),
        lot_id=lot.lot_id,
        owner_id=lot.owner_id,
        label=req.label,
        api_key_hash=hash_sensor_key(api_key),
        active=True,
    )
    db.add(sensor)
    db.commit()
    db.refresh(sensor)
    resp = _to_response(sensor)
    return SensorCreateResponse(**resp.model_dump(), api_key=api_key)


@router.get("", response_model=List[SensorResponse])
async def list_sensors(
    lot_id: Optional[str] = Query(None, description="Filter by lot"),
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    require_role(user, {"admin", "lot_owner"})
    q = db.query(Sensor)
    if user.get("role") != "admin":
        caller = db.query(User).filter(User.email == user.get("sub")).first()
        owned = (
            db.query(ParkingLot.lot_id)
            .filter(ParkingLot.owner_id == (caller.id if caller else -1))
            .all()
        )
        owned_ids = {row[0] for row in owned}
        q = q.filter(Sensor.lot_id.in_(owned_ids)) if owned_ids else q.filter(
            Sensor.id == -1
        )
    if lot_id:
        q = q.filter(Sensor.lot_id == lot_id)
    return [_to_response(s) for s in q.all()]


@router.get("/{sensor_id}", response_model=SensorResponse)
async def get_sensor(
    sensor_id: str = Path(..., description="Sensor public id"),
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    require_role(user, {"admin", "lot_owner"})
    sensor = db.query(Sensor).filter(Sensor.sensor_id == sensor_id).first()
    if not sensor:
        raise HTTPException(404, "Sensor not found")
    _assert_owner_or_admin(user, _get_lot_or_404(sensor.lot_id, db), db)
    return _to_response(sensor)


@router.patch("/{sensor_id}", response_model=SensorResponse)
async def update_sensor(
    req: SensorUpdateRequest,
    sensor_id: str = Path(..., description="Sensor public id"),
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    require_role(user, {"admin", "lot_owner"})
    sensor = db.query(Sensor).filter(Sensor.sensor_id == sensor_id).first()
    if not sensor:
        raise HTTPException(404, "Sensor not found")
    _assert_owner_or_admin(user, _get_lot_or_404(sensor.lot_id, db), db)
    if req.label is not None:
        sensor.label = req.label
    if req.active is not None:
        sensor.active = req.active
    db.commit()
    db.refresh(sensor)
    return _to_response(sensor)


@router.post("/{sensor_id}/rotate", response_model=SensorRotateResponse)
async def rotate_sensor(
    sensor_id: str = Path(..., description="Sensor public id"),
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    require_role(user, {"admin", "lot_owner"})
    sensor = db.query(Sensor).filter(Sensor.sensor_id == sensor_id).first()
    if not sensor:
        raise HTTPException(404, "Sensor not found")
    _assert_owner_or_admin(user, _get_lot_or_404(sensor.lot_id, db), db)
    api_key = generate_sensor_key()
    sensor.api_key_hash = hash_sensor_key(api_key)
    sensor.active = True
    db.commit()
    return SensorRotateResponse(
        sensor_id=sensor.sensor_id, lot_id=sensor.lot_id, api_key=api_key
    )


@router.delete("/{sensor_id}", status_code=204)
async def delete_sensor(
    sensor_id: str = Path(..., description="Sensor public id"),
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    require_role(user, {"admin", "lot_owner"})
    sensor = db.query(Sensor).filter(Sensor.sensor_id == sensor_id).first()
    if not sensor:
        raise HTTPException(404, "Sensor not found")
    _assert_owner_or_admin(user, _get_lot_or_404(sensor.lot_id, db), db)
    db.delete(sensor)
    db.commit()
