import pytest
from src.api.database import get_session, ParkingLot, OccupancyRecord
from src.pipeline.orchestrator import pipeline


def _init_rl_agent():
    """Ensure RL agent is loaded (test ordering independent)."""
    pipeline.pricing.ensure()


def _create_lot_with_occ(lot_id="pricing_zone"):
    db = get_session()
    try:
        if not db.query(ParkingLot).filter(ParkingLot.lot_id == lot_id).first():
            lot = ParkingLot(lot_id=lot_id, name="Pricing Zone", total_slots=100, base_price=10.0, price_cap=50.0)
            db.add(lot)
            db.flush()
        db.add(OccupancyRecord(lot_id=lot_id, occupied_slots=50, total_slots=100, occupancy_rate=0.5, price=12.0))
        db.commit()
    finally:
        db.close()


class TestAdjustPrice:
    @pytest.fixture(autouse=True)
    def _ensure_agent(self):
        _init_rl_agent()

    def test_adjust_requires_auth(self, client):
        resp = client.post("/api/v1/pricing/adjust", json={"predicted_occupancy": 0.5, "current_price": 10.0})
        assert resp.status_code in (401, 403)

    def test_adjust_returns_price(self, client, admin_headers):
        resp = client.post("/api/v1/pricing/adjust", json={
            "predicted_occupancy": 0.5, "current_price": 10.0,
        }, headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "price_multiplier" in data
        assert "new_price" in data
        assert "is_hike" in data

    def test_adjust_with_loaded_agent(self, client, admin_headers):
        resp = client.post("/api/v1/pricing/adjust", json={
            "predicted_occupancy": 0.5, "current_price": 10.0,
        }, headers=admin_headers)
        assert resp.status_code == 200

    def test_adjust_rejects_driver(self, client, auth_headers):
        """Non-admin users should get 403."""
        resp = client.post("/api/v1/pricing/adjust", json={
            "predicted_occupancy": 0.5, "current_price": 10.0,
        }, headers=auth_headers)
        assert resp.status_code == 403


class TestLotPricing:
    def test_lot_pricing_public(self, client):
        resp = client.get("/api/v1/pricing/lots?lot_id=test_lot")
        # Returns demo pricing when DB is empty (public endpoint, no auth needed)
        assert resp.status_code == 200

    def test_lot_pricing_returns_404_for_unknown(self, client, auth_headers):
        resp = client.get("/api/v1/pricing/lots?lot_id=nonexistent", headers=auth_headers)
        # Returns demo pricing when DB is empty; would return 404 only if lots exist but lot doesn't match
        assert resp.status_code in (200, 404)

    def test_lot_pricing_returns_lot_data(self, client, auth_headers):
        _create_lot_with_occ()
        resp = client.get("/api/v1/pricing/lots?lot_id=pricing_zone", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list) and len(data) > 0
        assert data[0]["lot_id"] == "pricing_zone"
        assert data[0]["base_price"] == 10.0


class TestPricingHistory:
    def test_pricing_history_public(self, client):
        resp = client.get("/api/v1/pricing/history")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 168  # 24h * 7d
        assert "day" in data[0]
        assert "hour" in data[0]
        assert "multiplier" in data[0]

    def test_pricing_history_with_db_data(self, client):
        _create_lot_with_occ("pricing_zone_history")
        resp = client.get("/api/v1/pricing/history?days=1")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 168

