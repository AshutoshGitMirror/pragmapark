import time
import pytest
from datetime import datetime, timezone, timedelta

from src.micro.state_engine import slot_state_engine
from src.api.routes.micro import _prebook_limiter


def _clear_prebook_state():
    slot_state_engine._states.clear()
    slot_state_engine._timestamps.clear()
    slot_state_engine._reservations.clear()
    slot_state_engine._reservation_expiry.clear()
    slot_state_engine._prebook_drivers.clear()
    slot_state_engine._prebook_expiry.clear()
    slot_state_engine._prebook_target.clear()
    slot_state_engine._last_cleanup = 0.0


def _clear_prebook_limiter():
    _prebook_limiter._buckets.clear()


@pytest.fixture(autouse=True)
def _reset_prebook_state():
    _clear_prebook_state()
    _clear_prebook_limiter()


class TestPrebookAPI:

    @pytest.fixture
    def seeded_lot(self, client, admin_headers):
        client.post("/api/v1/lots", json={
            "lot_id": "prebook_test_lot",
            "name": "Prebook Test Lot",
            "total_slots": 50,
            "base_price": 10.0,
        }, headers=admin_headers)
        client.post("/api/v1/micro/lots/prebook_test_lot/slots/seed", headers=admin_headers)
        return "prebook_test_lot"

    @pytest.fixture
    def alt_auth_headers(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "email": "alt_driver_prebook@pragma.io",
            "password": "AltPass123!",
            "full_name": "Alt Driver",
        })
        assert resp.status_code == 200, resp.text
        token = resp.json().get("access_token", "")
        return {"Authorization": f"Bearer {token}"}

    @staticmethod
    def _target_1h():
        return (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

    def test_prebook_flow(self, client, auth_headers, admin_headers, seeded_lot):
        target = self._target_1h()
        resp = client.post("/api/v1/micro/prebook", json={
            "lot_id": seeded_lot,
            "slots": [
                {"slot_index": 1, "priority": 1},
                {"slot_index": 2, "priority": 2},
            ],
            "target_time": target,
        }, headers=auth_headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["assigned_slot_index"] in (1, 2)
        assert data["probability"] > 0
        assert data["fallback_order"] is not None
        assert data["status"] == "active"
        assert data["prebook_id"] != ""

    def test_confirm_prebook(self, client, auth_headers, admin_headers, seeded_lot):
        target = self._target_1h()
        prebook = client.post("/api/v1/micro/prebook", json={
            "lot_id": seeded_lot,
            "slots": [{"slot_index": 3, "priority": 1}],
            "target_time": target,
        }, headers=auth_headers)
        assert prebook.status_code == 200, prebook.text
        prebook_id = prebook.json()["prebook_id"]

        resp = client.post("/api/v1/micro/confirm", json={
            "prebook_id": prebook_id,
        }, headers=auth_headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["session_id"] != ""
        assert data["status"] == "confirmed"
        assert data["prebook_id"] == prebook_id

    def test_prebook_expired(self, client, auth_headers, admin_headers, seeded_lot):
        past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        prebook = client.post("/api/v1/micro/prebook", json={
            "lot_id": seeded_lot,
            "slots": [{"slot_index": 4, "priority": 1}],
            "target_time": past,
        }, headers=auth_headers)
        assert prebook.status_code == 200, prebook.text
        prebook_id = prebook.json()["prebook_id"]

        resp = client.post("/api/v1/micro/confirm", json={
            "prebook_id": prebook_id,
        }, headers=auth_headers)
        assert resp.status_code == 410, resp.text

    def test_prebook_no_slots_available(self, client, auth_headers, alt_auth_headers, admin_headers, seeded_lot):
        target = self._target_1h()
        r1 = client.post("/api/v1/micro/prebook", json={
            "lot_id": seeded_lot,
            "slots": [{"slot_index": 5, "priority": 1}],
            "target_time": target,
        }, headers=auth_headers)
        assert r1.status_code == 200, r1.text

        r2 = client.post("/api/v1/micro/prebook", json={
            "lot_id": seeded_lot,
            "slots": [{"slot_index": 5, "priority": 1}],
            "target_time": target,
        }, headers=alt_auth_headers)
        assert r2.status_code == 409, r2.text

    def test_prebook_rate_limit(self, client, auth_headers, admin_headers, seeded_lot):
        target = self._target_1h()
        for i in range(5):
            resp = client.post("/api/v1/micro/prebook", json={
                "lot_id": seeded_lot,
                "slots": [{"slot_index": 10 + i, "priority": 1}],
                "target_time": target,
            }, headers=auth_headers)
            assert resp.status_code == 200, f"Prebook {i + 1}: {resp.text}"
        resp = client.post("/api/v1/micro/prebook", json={
            "lot_id": seeded_lot,
            "slots": [{"slot_index": 99, "priority": 1}],
            "target_time": target,
        }, headers=auth_headers)
        assert resp.status_code == 429, resp.text
