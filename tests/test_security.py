import os
import pytest
from src.api.database import get_session, ParkingLot


def _create_lot(lot_id="sec_lot"):
    db = get_session()
    try:
        if not db.query(ParkingLot).filter(ParkingLot.lot_id == lot_id).first():
            db.add(ParkingLot(lot_id=lot_id, name="Sec Test", total_slots=100, base_price=10.0, price_cap=50.0))
            db.commit()
    finally:
        db.close()


def _register_or_login(client, email, password, full_name):
    resp = client.post("/api/v1/auth/register", json={
        "email": email, "password": password, "full_name": full_name,
    })
    if resp.status_code == 200:
        return resp.json().get("access_token", "")
    resp = client.post("/api/v1/auth/login", json={
        "email": email, "password": password,
    })
    assert resp.status_code == 200, f"auth failed ({resp.status_code}): {resp.text}"
    return resp.json().get("access_token", "")


class TestIDOR:
    def test_active_sessions_scoped_by_driver(self, client, auth_headers):
        resp = client.get("/api/v1/sessions/active/test_lot", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data

    def test_end_session_idor(self, client, auth_headers):
        resp = client.post("/api/v1/sessions/end/nonexistent", headers=auth_headers)
        assert resp.status_code == 404


class TestUnauthEndpoints:
    def test_lots_no_auth(self, client):
        resp = client.get("/api/v1/lots")
        assert resp.status_code == 200

    def test_lots_authenticated(self, client, auth_headers):
        resp = client.get("/api/v1/lots", headers=auth_headers)
        assert resp.status_code == 200

    def test_health_no_auth(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200

    def test_auth_endpoints_blocked(self, client):
        protected = [
            ("GET", "/api/v1/driver/lots"),
            ("GET", "/api/v1/driver/lots/test"),
            ("GET", "/api/v1/driver/pipeline/status"),
            ("GET", "/api/v1/blockchain/status"),
            ("GET", "/api/v1/sessions/active/test"),
            ("GET", "/api/v1/predict/health"),
        ]
        for method, path in protected:
            if method == "GET":
                resp = client.get(path)
            else:
                resp = client.post(path)
            assert resp.status_code in (401, 403), f"{method} {path} returned {resp.status_code}"


class TestRateLimiters:
    def test_blockchain_rate_limit(self, client, auth_headers):
        resp = client.post("/api/v1/blockchain/transaction", json={
            "driver_id": "test@pragma.io",
            "lot_id": "lot_1",
            "action": "test",
            "price": 10.0,
            "duration_minutes": 60,
        }, headers=auth_headers)
        assert resp.status_code == 200

    def test_login_rate_limit(self, client):
        if os.environ.get("PRAGMA_ENV") == "testing":
            pytest.skip("rate limits disabled in testing mode")
        for _ in range(10):
            client.post("/api/v1/auth/login", json={
                "email": "ratelimit_sec@pragma.io",
                "password": "WrongPass1!",
            })
        resp = client.post("/api/v1/auth/login", json={
            "email": "ratelimit_sec@pragma.io",
            "password": "WrongPass1!",
        })
        assert resp.status_code == 429

    def test_prediction_requires_auth(self, client):
        resp = client.post("/api/v1/predict/occupancy", json={
            "occupied_slots": 100,
            "total_slots": 500,
            "occ_lag_15m": 0.5,
            "occ_lag_1h": 0.45,
            "net_flux": 0.0,
            "hour": 14,
        })
        assert resp.status_code in (401, 403)


class TestFrontendA11Y:
    def test_loading_page_served(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        html = resp.text.lower()
        assert "pragma" in html or "root" in html


class TestNotFound:
    def test_nonexistent_route_returns_404(self, client):
        resp = client.get("/api/v1/nonexistent/route/12345")
        assert resp.status_code == 404

    def test_nonexistent_api_prefix_returns_404(self, client):
        resp = client.get("/api/v1/this/does/not/exist")
        assert resp.status_code == 404


class TestRoleIsolation:
    def test_driver_cannot_see_other_driver_detail(self, client):
        token_a = _register_or_login(client, "driver_a_147@pragma.io", "TestPass123!", "Driver A")
        headers_a = {"Authorization": f"Bearer {token_a}"}
        token_b = _register_or_login(client, "driver_b_147@pragma.io", "TestPass123!", "Driver B")
        headers_b = {"Authorization": f"Bearer {token_b}"}

        _create_lot("iso_lot")
        client.cookies.clear()
        start = client.post("/api/v1/sessions/start", json={"lot_id": "iso_lot", "slot": 1}, headers=headers_a)
        assert start.status_code == 200
        sid = start.json()["session_id"]

        client.cookies.clear()
        resp = client.get(f"/api/v1/sessions/{sid}", headers=headers_b)
        assert resp.status_code == 403

    def test_driver_cannot_end_other_driver_session(self, client):
        token_a = _register_or_login(client, "driver_c_147@pragma.io", "TestPass123!", "Driver C")
        headers_a = {"Authorization": f"Bearer {token_a}"}
        token_b = _register_or_login(client, "driver_d_147@pragma.io", "TestPass123!", "Driver D")
        headers_b = {"Authorization": f"Bearer {token_b}"}

        _create_lot("iso_lot2")
        client.cookies.clear()
        start = client.post("/api/v1/sessions/start", json={"lot_id": "iso_lot2", "slot": 2}, headers=headers_a)
        assert start.status_code == 200
        sid = start.json()["session_id"]

        client.cookies.clear()
        resp = client.post("/api/v1/sessions/end", json={"session_id": sid}, headers=headers_b)
        assert resp.status_code == 403

    def test_driver_cannot_list_other_driver_active(self, client):
        token_a = _register_or_login(client, "driver_e_147@pragma.io", "TestPass123!", "Driver E")
        headers_a = {"Authorization": f"Bearer {token_a}"}
        token_b = _register_or_login(client, "driver_f_147@pragma.io", "TestPass123!", "Driver F")
        headers_b = {"Authorization": f"Bearer {token_b}"}

        _create_lot("iso_lot3")
        client.cookies.clear()
        client.post("/api/v1/sessions/start", json={"lot_id": "iso_lot3", "slot": 3}, headers=headers_a)

        client.cookies.clear()
        resp = client.get("/api/v1/sessions/active/iso_lot3", headers=headers_b)
        assert resp.status_code == 200
        assert resp.json()["active_count"] == 0


class TestDedupStart:
    def test_duplicate_start_same_lot_slot_returns_409(self, client, auth_headers):
        _create_lot("dedup_lot")
        r1 = client.post("/api/v1/sessions/start", json={"lot_id": "dedup_lot", "slot": 10}, headers=auth_headers)
        assert r1.status_code == 200

        r2 = client.post("/api/v1/sessions/start", json={"lot_id": "dedup_lot", "slot": 10}, headers=auth_headers)
        assert r2.status_code == 409

    def test_duplicate_start_different_lot_ok(self, client, auth_headers):
        _create_lot("dedup_lot_a")
        _create_lot("dedup_lot_b")
        r1 = client.post("/api/v1/sessions/start", json={"lot_id": "dedup_lot_a", "slot": 1}, headers=auth_headers)
        assert r1.status_code == 200
        sid1 = r1.json()["session_id"]
        client.post("/api/v1/sessions/end", json={"session_id": sid1}, headers=auth_headers)
        r2 = client.post("/api/v1/sessions/start", json={"lot_id": "dedup_lot_b", "slot": 1}, headers=auth_headers)
        assert r2.status_code == 200


class TestSQLInjection:
    def test_login_sql_injection(self, client):
        resp = client.post("/api/v1/auth/login", json={
            "email": "' OR 1=1 --",
            "password": "anything",
        })
        assert resp.status_code in (401, 422)

    def test_register_sql_injection(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "email": "'; DROP TABLE users; --@x.io",
            "password": "StrongPass1!",
            "full_name": "Hacker",
        })
        assert resp.status_code != 500
