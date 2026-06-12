from src.pipeline.orchestrator import pipeline


class TestActuatorStatus:
    def test_status_requires_admin(self, client, auth_headers):
        resp = client.get("/api/v1/actuator/status", headers=auth_headers)
        assert resp.status_code == 403

    def test_status_requires_auth(self, client):
        resp = client.get("/api/v1/actuator/status")
        assert resp.status_code in (401, 403)

    def test_status_returns_summary_and_zones(self, client, admin_headers):
        resp = client.get("/api/v1/actuator/status", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "zones" in data
        assert "zones_registered" in data["summary"]
        assert "total_commands" in data["summary"]
        assert isinstance(data["zones"], list)

    def test_status_zones_have_actuator_fields(self, client, admin_headers):
        resp = client.get("/api/v1/actuator/status", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        for zone in data["zones"]:
            assert "zone_id" in zone
            assert "barrier" in zone
            assert "pricing_board" in zone
            assert "congestion_light" in zone
            assert "barrier_id" in zone["barrier"]
            assert "open" in zone["barrier"]
            assert "board_id" in zone["pricing_board"]
            assert "displayed_price" in zone["pricing_board"]
            assert "light_id" in zone["congestion_light"]
            assert "color" in zone["congestion_light"]

    def test_status_matches_running_pipeline(self, client, admin_headers):
        summary = pipeline.actuator.summary()
        resp = client.get("/api/v1/actuator/status", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert (
            data["summary"]["zones_registered"] == summary["zones_registered"]
        )
        assert data["summary"]["total_commands"] == summary["total_commands"]
