from src.api.schemas import DashboardResponse, SystemHealthResponse


class TestAdminDashboard:
    def test_dashboard_requires_admin(self, client, auth_headers):
        resp = client.get("/api/v1/admin/dashboard", headers=auth_headers)
        assert resp.status_code == 403

    def test_dashboard_returns_metrics(self, client, admin_headers):
        resp = client.get("/api/v1/admin/dashboard", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_lots" in data
        assert "total_users" in data
        assert "total_revenue" in data
        assert "system_occupancy" in data

    def test_dashboard_requires_auth(self, client):
        resp = client.get("/api/v1/admin/dashboard")
        assert resp.status_code in (401, 403)

    def test_dashboard_matches_pydantic_schema(self, client, admin_headers):
        resp = client.get("/api/v1/admin/dashboard", headers=admin_headers)
        assert resp.status_code == 200
        validated = DashboardResponse(**resp.json())
        assert validated.total_lots >= 0
        assert validated.total_revenue >= 0


class TestSystemHealth:
    def test_health_requires_admin(self, client, auth_headers):
        resp = client.get("/api/v1/admin/system-health", headers=auth_headers)
        assert resp.status_code == 403

    def test_health_returns_status(self, client, admin_headers):
        resp = client.get("/api/v1/admin/system-health", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "transactions_last_hour" in data
        assert "layers" in data

    def test_health_digital_twin_labeled_simulated(self, client, admin_headers):
        resp = client.get("/api/v1/admin/system-health", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["layers"].get("digital_twin") == "simulated"

    def test_health_uses_simulated_for_fallback_layers(self, client, admin_headers):
        resp = client.get("/api/v1/admin/system-health", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "simulated" in str(data["layers"].values())

    def test_health_is_deterministic(self, client, admin_headers):
        r1 = client.get("/api/v1/admin/system-health", headers=admin_headers)
        r2 = client.get("/api/v1/admin/system-health", headers=admin_headers)
        assert r1.json() == r2.json()

    def test_health_matches_pydantic_schema(self, client, admin_headers):
        resp = client.get("/api/v1/admin/system-health", headers=admin_headers)
        assert resp.status_code == 200
        validated = SystemHealthResponse(**resp.json())
        assert validated.status in ("healthy", "degraded")
        assert isinstance(validated.layers, dict)
