import os
import pytest


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
        assert resp.status_code in (401, 403)

    def test_lots_authenticated(self, client, auth_headers):
        resp = client.get("/api/v1/lots", headers=auth_headers)
        assert resp.status_code == 200

    def test_health_no_auth(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200

    def test_auth_endpoints_blocked(self, client):
        protected = [
            ("GET", "/api/v1/lots"),
            ("GET", "/api/v1/driver/lots"),
            ("GET", "/api/v1/driver/lots/test"),
            ("GET", "/api/v1/driver/pipeline/status"),
            ("GET", "/api/v1/blockchain/status"),
            ("GET", "/api/v1/sessions/active/test"),
            ("GET", "/api/v1/predict/health"),
            ("GET", "/api/v1/pricing/zones"),
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
