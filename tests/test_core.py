import os
import pytest


class TestHealth:
    def test_health_endpoint(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "models" in data
        assert "blockchain" in data

    def test_ready_endpoint(self, client):
        resp = client.get("/api/v1/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert "ready" in data
        assert "database" in data
        assert "models_loaded" in data


class TestParkingLots:
    def test_list_lots(self, client, auth_headers):
        resp = client.get("/api/v1/lots", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_get_lot_by_id(self, client, auth_headers):
        resp = client.get("/api/v1/lots/nonexistent", headers=auth_headers)
        assert resp.status_code == 404


class TestDriverLots:
    def test_driver_lots_requires_auth(self, client):
        resp = client.get("/api/v1/driver/lots")
        assert resp.status_code in (401, 403)

    def test_driver_lot_detail_requires_auth(self, client):
        resp = client.get("/api/v1/driver/lots/test_lot")
        assert resp.status_code in (401, 403)

    def test_driver_lots_authenticated(self, client, auth_headers):
        resp = client.get("/api/v1/driver/lots", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "lots" in data


class TestRateLimiting:
    def test_global_rate_limit(self, client):
        for _ in range(5):
            client.get("/api/v1/health")
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200

    def test_register_rate_limit(self, client):
        if os.environ.get("PRAGMA_ENV") == "testing":
            pytest.skip("rate limits disabled in testing mode")
        for _ in range(6):
            client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"ratelimit{_}@pragma.io",
                    "password": "RateLimit1!",
                    "full_name": "Rate Limit",
                },
            )
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "banned@pragma.io",
                "password": "RateLimit1!",
                "full_name": "Banned",
            },
        )
        assert resp.status_code == 429


class TestPipeline:
    def test_pipeline_status_requires_auth(self, client):
        resp = client.get("/api/v1/driver/pipeline/status")
        assert resp.status_code in (401, 403)

    def test_pipeline_status_authenticated(self, client, auth_headers):
        resp = client.get(
            "/api/v1/driver/pipeline/status", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "ml_models" in data
        assert "blockchain" in data
