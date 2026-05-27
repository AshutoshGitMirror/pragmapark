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
