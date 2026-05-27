import os


class TestPredictOccupancy:
    def test_predict_requires_auth(self, client):
        resp = client.post("/api/v1/predict/occupancy", json={
            "occupied_slots": 50, "total_slots": 100, "occ_lag_15m": 0.4,
            "occ_lag_1h": 0.3, "net_flux": 0.0, "hour": 14,
        })
        assert resp.status_code in (401, 403)

    def test_predict_returns_503_when_no_models(self, client, auth_headers, monkeypatch):
        import src.api.routes.prediction as pred
        monkeypatch.setattr(pred, "_load_models", lambda: (None, None))
        resp = client.post("/api/v1/predict/occupancy", json={
            "occupied_slots": 50, "total_slots": 100, "occ_lag_15m": 0.4,
            "occ_lag_1h": 0.3, "net_flux": 0.0, "hour": 14,
        }, headers=auth_headers)
        assert resp.status_code == 503


class TestModelHealth:
    def test_health_requires_auth(self, client):
        resp = client.get("/api/v1/predict/health")
        assert resp.status_code in (401, 403)

    def test_health_returns_loaded_status(self, client, auth_headers):
        resp = client.get("/api/v1/predict/health", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "rf_loaded" in data
        assert "xgb_loaded" in data
        assert "status" in data
