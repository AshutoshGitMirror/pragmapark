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


class TestLotPredictionsRoute:
    def test_lot_predictions_public(self, client):
        resp = client.get("/api/v1/lots/A1/predictions")
        assert resp.status_code in (200, 404)

    def test_lot_predictions_returns_predictions(self, client, monkeypatch):
        from src.api.database import get_session, ParkingLot, OccupancyRecord
        import src.api.routes.prediction as pred
        
        class MockModel:
            def predict(self, X):
                import numpy as np
                return np.array([0.5])
                
        monkeypatch.setattr(pred, "_load_models", lambda: (MockModel(), MockModel()))
        
        db = get_session()
        try:
            if not db.query(ParkingLot).filter(ParkingLot.lot_id == "pred_test_lot").first():
                lot = ParkingLot(lot_id="pred_test_lot", name="Prediction Test Lot", total_slots=100, base_price=10.0)
                db.add(lot)
                db.flush()
            import datetime
            now = datetime.datetime.now(datetime.timezone.utc)
            for i in range(10):
                ts = now - datetime.timedelta(minutes=15 * (10 - i))
                db.add(OccupancyRecord(lot_id="pred_test_lot", occupied_slots=40 + i, total_slots=100, occupancy_rate=0.4 + i*0.01, price=12.0, timestamp=ts))
            db.commit()
        finally:
            db.close()
            
        resp = client.get("/api/v1/lots/pred_test_lot/predictions?hours=2")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "predicted_occupancy_rate" in data[0]
        assert "actual_occupancy_rate" in data[0]

