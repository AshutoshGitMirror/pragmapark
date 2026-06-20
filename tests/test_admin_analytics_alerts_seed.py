from src.api.schemas.admin import AnalyticsResponse, AlertItem


class TestAdminAnalytics:
    def test_analytics_requires_admin(self, client, auth_headers):
        resp = client.get("/api/v1/admin/analytics", headers=auth_headers)
        assert resp.status_code == 403

    def test_analytics_requires_auth(self, client):
        resp = client.get("/api/v1/admin/analytics")
        assert resp.status_code in (401, 403)

    def test_analytics_returns_hourly_occupancy(self, client, admin_headers):
        resp = client.get("/api/v1/admin/analytics", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "hourly_occupancy" in data
        assert isinstance(data["hourly_occupancy"], list)
        if data["hourly_occupancy"]:
            entry = data["hourly_occupancy"][0]
            assert "hour" in entry
            assert "rate" in entry

    def test_analytics_returns_lot_comparison(self, client, admin_headers):
        resp = client.get("/api/v1/admin/analytics", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "lot_comparison" in data
        assert isinstance(data["lot_comparison"], list)
        if data["lot_comparison"]:
            entry = data["lot_comparison"][0]
            assert "lot_id" in entry
            assert "name" in entry
            assert "occupancy" in entry
            assert "revenue" in entry

    def test_analytics_returns_system_performance(self, client, admin_headers):
        resp = client.get("/api/v1/admin/analytics", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "system_performance" in data
        assert isinstance(data["system_performance"], list)
        metrics = {m["metric"] for m in data["system_performance"]}
        assert "Avg Occupancy" in metrics
        assert "Blockchain Height" in metrics

    def test_analytics_matches_pydantic_schema(self, client, admin_headers):
        resp = client.get("/api/v1/admin/analytics", headers=admin_headers)
        assert resp.status_code == 200
        validated = AnalyticsResponse(**resp.json())
        assert isinstance(validated.hourly_occupancy, list)
        assert isinstance(validated.lot_comparison, list)

    def test_analytics_is_deterministic(self, client, admin_headers):
        r1 = client.get("/api/v1/admin/analytics", headers=admin_headers)
        r2 = client.get("/api/v1/admin/analytics", headers=admin_headers)
        assert r1.json() == r2.json()


class TestAdminAlerts:
    def test_alerts_requires_admin(self, client, auth_headers):
        resp = client.get("/api/v1/admin/alerts", headers=auth_headers)
        assert resp.status_code == 403

    def test_alerts_requires_auth(self, client):
        resp = client.get("/api/v1/admin/alerts")
        assert resp.status_code in (401, 403)

    def test_alerts_returns_empty_when_no_data(self, client, admin_headers):
        resp = client.get("/api/v1/admin/alerts", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_alerts_returned_items_match_schema(self, client, admin_headers):
        resp = client.get("/api/v1/admin/alerts", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        for item in data:
            assert "id" in item
            assert "type" in item
            assert "severity" in item
            assert "message" in item

    def test_alerts_matches_pydantic_schema(self, client, admin_headers):
        resp = client.get("/api/v1/admin/alerts", headers=admin_headers)
        assert resp.status_code == 200
        for item in resp.json():
            validated = AlertItem(**item)
            assert validated.severity in ("warning", "info", "critical")

    def test_resolve_alert_requires_admin(self, client, auth_headers):
        resp = client.put(
            "/api/v1/admin/alerts/1/resolve", headers=auth_headers
        )
        assert resp.status_code == 403

    def test_resolve_alert_returns_status(self, client, admin_headers):
        resp = client.put(
            "/api/v1/admin/alerts/1/resolve", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "resolved"
        assert data["alert_id"] == 1


