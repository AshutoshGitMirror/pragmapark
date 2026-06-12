class TestSimulationStatus:
    def test_status_requires_auth(self, client):
        resp = client.get("/api/v1/simulation/status")
        assert resp.status_code in (401, 403)

    def test_status_returns_simulation_info(self, client, auth_headers):
        resp = client.get("/api/v1/simulation/status", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "speedup" in data
        assert "is_fast_forwarding" in data
        assert "real_time" in data
        assert "snapshot_exists" in data
        assert isinstance(data["speedup"], int)
        assert isinstance(data["is_fast_forwarding"], bool)
        assert isinstance(data["snapshot_exists"], bool)

    def test_status_default_speedup_is_1(self, client, auth_headers):
        resp = client.get("/api/v1/simulation/status", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["speedup"] == 1


class TestSimulationSpeed:
    def test_speed_requires_admin(self, client, auth_headers):
        resp = client.post(
            "/api/v1/simulation/speed",
            json={"speedup": 10},
            headers=auth_headers,
        )
        assert resp.status_code == 403

    def test_speed_requires_auth(self, client):
        resp = client.post("/api/v1/simulation/speed", json={"speedup": 10})
        assert resp.status_code in (401, 403)

    def test_speed_returns_updated_value(self, client, admin_headers):
        from src.simulation.time_machine import time_machine

        original = time_machine.speedup
        try:
            resp = client.post(
                "/api/v1/simulation/speed",
                json={"speedup": 60},
                headers=admin_headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["speedup"] == 60
            assert data["is_fast_forwarding"] is True
        finally:
            time_machine.set_speedup(original)

    def test_speed_resets_simulation(self, client, admin_headers):
        from src.simulation.time_machine import time_machine

        original = time_machine.speedup
        try:
            resp = client.post(
                "/api/v1/simulation/speed",
                json={"speedup": 1},
                headers=admin_headers,
            )
            assert resp.status_code == 200
            assert resp.json()["is_fast_forwarding"] is False
        finally:
            time_machine.set_speedup(original)

    def test_speed_invalid_speedup_rejected(self, client, admin_headers):
        resp = client.post(
            "/api/v1/simulation/speed",
            json={"speedup": 0},
            headers=admin_headers,
        )
        assert resp.status_code in (400, 422)

    def test_speed_too_high_speedup_rejected(self, client, admin_headers):
        resp = client.post(
            "/api/v1/simulation/speed",
            json={"speedup": 999999},
            headers=admin_headers,
        )
        assert resp.status_code in (400, 422)


class TestSimulationReset:
    def test_reset_requires_admin(self, client, auth_headers):
        resp = client.post("/api/v1/simulation/reset", headers=auth_headers)
        assert resp.status_code == 403

    def test_reset_requires_auth(self, client):
        resp = client.post("/api/v1/simulation/reset")
        assert resp.status_code in (401, 403)

    def test_reset_without_snapshot_returns_error(self, client, admin_headers):
        from src.simulation.time_machine import time_machine

        original_path = time_machine.snapshot_path
        try:
            time_machine.snapshot_path = None
            resp = client.post(
                "/api/v1/simulation/reset", headers=admin_headers
            )
            assert resp.status_code == 200
            assert resp.json()["success"] is False
        finally:
            time_machine.snapshot_path = original_path

    def test_reset_returns_response_schema(self, client, admin_headers):
        resp = client.post("/api/v1/simulation/reset", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "success" in data
        assert "message" in data


class TestSimulationSnapshot:
    def test_snapshot_requires_admin(self, client, auth_headers):
        resp = client.post("/api/v1/simulation/snapshot", headers=auth_headers)
        assert resp.status_code == 403

    def test_snapshot_requires_auth(self, client):
        resp = client.post("/api/v1/simulation/snapshot")
        assert resp.status_code in (401, 403)

    def test_snapshot_returns_response_schema(self, client, admin_headers):
        resp = client.post(
            "/api/v1/simulation/snapshot", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "success" in data
        assert "message" in data
