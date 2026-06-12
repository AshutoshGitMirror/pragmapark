class TestRevenueCumulative:
    def test_cumulative_requires_admin(self, client, auth_headers):
        resp = client.get("/api/v1/revenue/cumulative", headers=auth_headers)
        assert resp.status_code == 403

    def test_cumulative_returns_zeros_when_empty(self, client, admin_headers):
        resp = client.get("/api/v1/revenue/cumulative", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_revenue"] == 0
        assert data["total_sessions"] == 0
        assert data["total_lots"] >= 0

    def test_cumulative_requires_auth(self, client):
        resp = client.get("/api/v1/revenue/cumulative")
        assert resp.status_code in (401, 403)


class TestRevenueOverview:
    def test_overview_requires_admin(self, client, auth_headers):
        resp = client.get("/api/v1/revenue/overview", headers=auth_headers)
        assert resp.status_code == 403

    def test_overview_returns_empty_daily(self, client, admin_headers):
        resp = client.get(
            "/api/v1/revenue/overview?days=7", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total_revenue" in data
        assert "daily" in data


class TestListTransactions:
    def test_transactions_requires_admin(self, client, auth_headers):
        resp = client.get("/api/v1/revenue/transactions", headers=auth_headers)
        assert resp.status_code == 403

    def test_transactions_returns_list(self, client, admin_headers):
        resp = client.get(
            "/api/v1/revenue/transactions", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
