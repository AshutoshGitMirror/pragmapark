import pytest
from datetime import datetime, timezone, timedelta

from src.digital_twin.simulator import TwinState
from src.digital_twin.generator import Generator
from src.micro.resident_map import slot_resident_mapping
from src.pipeline.orchestrator import pipeline


class TestResidentialDT:

    def test_twin_state_has_n_share_listed(self):
        ts = TwinState(
            timestamp=1000.0, zone_id="test_zone",
            occupancy_rate=0.5, price=10.0, total_slots=100,
            congestion_level="normal", n_share_listed=3,
        )
        assert ts.occupancy_rate == 0.5
        assert ts.price == 10.0
        assert ts.total_slots == 100
        assert ts.congestion_level == "normal"
        assert ts.n_share_listed == 3

    def test_generator_online_update_accepts_n_share_listed(self):
        gen = Generator()
        assert gen.state_dim == 5
        assert gen.cond_dim == 6
        assert gen.input_dim == 11

        result = gen.online_update(
            occ_rate=0.5, price=10.0, duration_hours=2.0,
            congestion="normal", n_share_listed=3,
        )

        assert hasattr(gen, '_online_buffer')
        assert hasattr(gen, '_online_steps')
        assert gen._online_steps == 0
        assert len(gen._online_buffer) == 1
        assert result["trained"] is False
        assert result["samples"] == 1

    def test_end_session_feeds_share_count(self, client, admin_headers, auth_headers):
        token = _register_or_login(
            client, "dt_driver@pragma.io", "DtPass123!", "DT Driver"
        )
        client.cookies.clear()
        dt_headers = {"Authorization": f"Bearer {token}"}

        resp = client.post("/api/v1/lots", json={
            "lot_id": "dt_lot", "name": "DT Lot",
            "total_slots": 10, "base_price": 10.0, "price_cap": 50.0,
        }, headers=admin_headers)
        assert resp.status_code == 200, resp.text

        resp = client.post("/api/v1/micro/lots/dt_lot/slots/seed", headers=admin_headers)
        assert resp.status_code == 200, resp.text

        resp = client.post("/api/v1/residential/permits", json={
            "lot_id": "dt_lot", "slot_index": 1, "permit_type": "monthly",
            "start_date": "2025-01-01", "end_date": "2025-12-31",
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        permit = resp.json()

        resp = client.post("/api/v1/residential/shares", json={
            "resident_profile_id": permit["id"], "price_per_hour": 5.0,
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text

        resp = client.post("/api/v1/sessions/start", json={
            "lot_id": "dt_lot", "slot": 1,
        }, headers=dt_headers)
        assert resp.status_code == 200, resp.text
        session_id = resp.json().get("session_id")
        assert session_id is not None

        resp = client.post("/api/v1/sessions/end", json={
            "session_id": session_id,
        }, headers=dt_headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "digital_twin" in data.get("layers_activated", [])

        dt = pipeline.dt
        assert dt is not None
        assert "dt_lot" in dt.zones
        assert "n_share_listed" in dt.zones["dt_lot"]
        assert dt.zones["dt_lot"]["n_share_listed"] >= 0

    def test_slot_resident_mapping_integration(self, client, admin_headers, auth_headers):
        resp = client.post("/api/v1/lots", json={
            "lot_id": "mapping_lot", "name": "Mapping Lot",
            "total_slots": 10, "base_price": 10.0, "price_cap": 50.0,
        }, headers=admin_headers)
        assert resp.status_code == 200, resp.text

        resp = client.post("/api/v1/micro/lots/mapping_lot/slots/seed", headers=admin_headers)
        assert resp.status_code == 200, resp.text

        resp = client.post("/api/v1/residential/permits", json={
            "lot_id": "mapping_lot", "slot_index": 1, "permit_type": "monthly",
            "start_date": "2025-01-01", "end_date": "2025-12-31",
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        permit = resp.json()

        resp = client.post("/api/v1/residential/shares", json={
            "resident_profile_id": permit["id"], "price_per_hour": 5.0,
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text

        slots = slot_resident_mapping.get_resident_slots("mapping_lot")
        shared_count = sum(1 for s in slots if s.is_shared)
        assert isinstance(shared_count, int)
        assert shared_count >= 1


def _register_or_login(client, email, password, full_name):
    resp = client.post("/api/v1/auth/register", json={
        "email": email, "password": password, "full_name": full_name,
    })
    if resp.status_code == 200:
        return resp.json().get("access_token", "")
    if resp.status_code == 400 and "already registered" in resp.text:
        from tests.conftest import _clear_rate_limiters
        resp = client.post("/api/v1/auth/login", json={
            "email": email, "password": password,
        })
        if resp.status_code == 429:
            _clear_rate_limiters()
            resp = client.post("/api/v1/auth/login", json={
                "email": email, "password": password,
            })
    assert resp.status_code == 200, (
        f"auth failed ({resp.status_code}): {resp.text}"
    )
    return resp.json().get("access_token", "")
