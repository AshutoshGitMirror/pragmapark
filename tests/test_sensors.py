"""Tests for the per-sensor API-key subsystem (Phase 1 sensor auth).

Covers: sensor CRUD (ownership-scoped), key rotation, deactivation, and
using an X-Sensor-Key to push real occupancy via the ingestion endpoint.
"""
import pytest
from src.api.database import (
    OccupancyRecord,
    ParkingLot,
    User,
    get_session,
)
from src.api.auth import hash_password


def _login(client, email, password):
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    if resp.status_code == 429:
        from tests.conftest import _clear_rate_limiters

        _clear_rate_limiters()
        resp = client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
    assert resp.status_code == 200, f"login failed: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _make_owner(client, email="owner@pragma.io", password="OwnerPass123!"):
    db = get_session()
    try:
        u = db.query(User).filter(User.email == email).first()
        if not u:
            u = User(
                email=email,
                hashed_password=hash_password(password),
                full_name="Owner",
                role="lot_owner",
            )
            db.add(u)
            db.commit()
            db.refresh(u)
        owner_id = u.id
    finally:
        db.close()
    headers = _login(client, email, password)
    client.cookies.clear()  # ensure no auth cookie leaks into later requests
    return headers, owner_id


def _make_lot(lot_owner_id=None, lot_id="L1", total_slots=10):
    db = get_session()
    try:
        lot = db.query(ParkingLot).filter(ParkingLot.lot_id == lot_id).first()
        if not lot:
            lot = ParkingLot(
                lot_id=lot_id,
                name="Lot One",
                city="Mumbai",
                total_slots=total_slots,
                base_price=10.0,
                latitude=19.0,
                longitude=72.8,
                owner_id=lot_owner_id,
            )
            db.add(lot)
            db.commit()
            db.refresh(lot)
        return lot.lot_id
    finally:
        db.close()


def _create_sensor(client, headers, lot_id, label="cam-1"):
    return client.post(
        "/api/v1/sensors",
        headers=headers,
        json={"lot_id": lot_id, "label": label},
    )


def test_create_sensor_success(client):
    headers, owner_id = _make_owner(client)
    _make_lot(owner_id)
    resp = _create_sensor(client, headers, "L1")
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["lot_id"] == "L1"
    assert data["owner_id"] == owner_id
    assert data["label"] == "cam-1"
    assert data["api_key"]  # plaintext key returned exactly once
    assert "api_key_hash" not in data  # hash never leaks
    assert data["active"] is True
    assert data["sensor_id"]


def test_create_sensor_for_unowned_lot_forbidden(client):
    headers, owner_id = _make_owner(client)
    _make_lot(owner_id, lot_id="L2", total_slots=8)  # owned
    _make_lot(lot_id="OTHER", total_slots=5)  # unowned -> not this owner's
    resp = _create_sensor(client, headers, "OTHER")
    assert resp.status_code == 403


def test_list_sensors_owner_scoped(client):
    headers, owner_id = _make_owner(client)
    _make_lot(owner_id)
    _create_sensor(client, headers, "L1", label="a")
    _create_sensor(client, headers, "L1", label="b")
    resp = client.get("/api/v1/sensors", headers=headers)
    assert resp.status_code == 200
    sensors = resp.json()
    assert len(sensors) == 2
    assert all(s["owner_id"] == owner_id for s in sensors)


def test_admin_sees_all_sensors(client, admin_headers):
    owner_headers, owner_id = _make_owner(client)
    _make_lot(owner_id)
    _create_sensor(client, owner_headers, "L1")
    resp = client.get("/api/v1/sensors", headers=admin_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_rotate_sensor_returns_new_key(client):
    headers, owner_id = _make_owner(client)
    _make_lot(owner_id)
    created = _create_sensor(client, headers, "L1").json()
    old_key = created["api_key"]
    rotate = client.post(
        f"/api/v1/sensors/{created['sensor_id']}/rotate", headers=headers
    )
    assert rotate.status_code == 200, rotate.text
    new_key = rotate.json()["api_key"]
    assert new_key != old_key


def test_update_and_delete_sensor(client):
    headers, owner_id = _make_owner(client)
    _make_lot(owner_id)
    created = _create_sensor(client, headers, "L1").json()
    sid = created["sensor_id"]
    upd = client.patch(
        f"/api/v1/sensors/{sid}", headers=headers, json={"active": False}
    )
    assert upd.status_code == 200
    assert upd.json()["active"] is False
    dele = client.delete(f"/api/v1/sensors/{sid}", headers=headers)
    assert dele.status_code == 204
    assert client.get(f"/api/v1/sensors/{sid}", headers=headers).status_code == 404


def test_ingestion_with_valid_sensor_key(client):
    headers, owner_id = _make_owner(client)
    _make_lot(owner_id, total_slots=10)
    created = _create_sensor(client, headers, "L1").json()
    key = created["api_key"]
    n = 10
    vision = [i % 2 == 0 for i in range(n)]
    resp = client.post(
        "/api/v1/ingestion/sensor-readings",
        headers={"X-Sensor-Key": key},
        json={
            "lot_id": "L1",
            "ultrasonic_readings": [False] * n,
            "vision_readings": vision,
        },
    )
    assert resp.status_code == 200, resp.text
    db = get_session()
    try:
        count = (
            db.query(OccupancyRecord)
            .filter(OccupancyRecord.lot_id == "L1")
            .count()
        )
        assert count >= 1
    finally:
        db.close()


def test_ingestion_sensor_key_wrong_lot_forbidden(client):
    headers, owner_id = _make_owner(client)
    _make_lot(owner_id)
    _make_lot(lot_id="OTHER2", total_slots=5)
    created = _create_sensor(client, headers, "L1").json()
    key = created["api_key"]
    resp = client.post(
        "/api/v1/ingestion/sensor-readings",
        headers={"X-Sensor-Key": key},
        json={
            "lot_id": "OTHER2",  # mismatch with sensor's bound lot
            "ultrasonic_readings": [False] * 5,
            "vision_readings": [True] * 5,
        },
    )
    assert resp.status_code == 403


def test_ingestion_bad_key_unauthorized(client):
    _make_lot(lot_id="L1", total_slots=4)
    resp = client.post(
        "/api/v1/ingestion/sensor-readings",
        headers={"X-Sensor-Key": "not-a-real-key"},
        json={
            "lot_id": "L1",
            "ultrasonic_readings": [False] * 4,
            "vision_readings": [True] * 4,
        },
    )
    assert resp.status_code == 401


def test_ingestion_inactive_sensor_rejected(client):
    headers, owner_id = _make_owner(client)
    _make_lot(owner_id)
    created = _create_sensor(client, headers, "L1").json()
    key = created["api_key"]
    client.patch(
        f"/api/v1/sensors/{created['sensor_id']}",
        headers=headers,
        json={"active": False},
    )
    resp = client.post(
        "/api/v1/ingestion/sensor-readings",
        headers={"X-Sensor-Key": key},
        json={
            "lot_id": "L1",
            "ultrasonic_readings": [False] * 10,
            "vision_readings": [True] * 10,
        },
    )
    assert resp.status_code == 401
