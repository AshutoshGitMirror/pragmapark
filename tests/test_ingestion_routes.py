from src.api.database import get_session, ParkingLot


class TestIngestOccupancy:
    def _create_lot(self, lot_id="ingest_lot"):
        db = get_session()
        try:
            if not db.query(ParkingLot).filter(ParkingLot.lot_id == lot_id).first():
                db.add(ParkingLot(lot_id=lot_id, name="Ingest Test", total_slots=100, base_price=10.0, price_cap=50.0))
                db.commit()
        finally:
            db.close()

    def test_ingest_requires_auth(self, client):
        resp = client.post("/api/v1/ingestion/occupancy", json={"lot_id": "x", "occupied_slots": 50, "total_slots": 100})
        assert resp.status_code in (401, 403)

    def test_ingest_requires_sensor_role(self, client, auth_headers):
        resp = client.post("/api/v1/ingestion/occupancy", json={"lot_id": "x", "occupied_slots": 50, "total_slots": 100}, headers=auth_headers)
        assert resp.status_code == 403

    def test_ingest_returns_404_for_bad_lot(self, client, admin_headers):
        resp = client.post("/api/v1/ingestion/occupancy", json={"lot_id": "nonexistent", "occupied_slots": 50, "total_slots": 100}, headers=admin_headers)
        assert resp.status_code == 404

    def test_ingest_success(self, client, admin_headers):
        self._create_lot()
        resp = client.post("/api/v1/ingestion/occupancy", json={"lot_id": "ingest_lot", "occupied_slots": 50, "total_slots": 100, "net_flux": 5.0}, headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ingested"
        assert data["lot_id"] == "ingest_lot"
        assert data["occupancy_rate"] == 0.5

    def test_ingest_creates_record(self, client, admin_headers):
        self._create_lot("ingest_lot2")
        client.post("/api/v1/ingestion/occupancy", json={"lot_id": "ingest_lot2", "occupied_slots": 75, "total_slots": 100}, headers=admin_headers)
        from src.api.database import OccupancyRecord
        db = get_session()
        try:
            recs = db.query(OccupancyRecord).filter(OccupancyRecord.lot_id == "ingest_lot2").all()
            assert len(recs) >= 1
            assert recs[0].occupancy_rate == 0.75
        finally:
            db.close()

    def test_ingest_sensor_readings_requires_auth(self, client):
        resp = client.post("/api/v1/ingestion/sensor-readings", json={"lot_id": "ingest_lot"})
        assert resp.status_code in (401, 403)

    def test_ingest_sensor_readings_success(self, client, admin_headers):
        self._create_lot("sensor_lot")
        payload = {
            "lot_id": "sensor_lot",
            "ultrasonic_readings": [True, False, True],
            "vision_readings": [True, True, True],
            "weather_factor": 0.15
        }
        resp = client.post("/api/v1/ingestion/sensor-readings", json=payload, headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ingested"
        assert data["lot_id"] == "sensor_lot"
        assert data["fused_count"] == 3
        assert data["weather_factor"] == 0.15
        # [True, False, True] fused with [True, True, True]:
        # Ultrasonic anchor: trust ultrasonic for disagreements: [True, False, True] -> occupancy rate 2/3 = 0.6667
        assert 0.66 <= data["occupancy_rate"] <= 0.67

    def test_ingest_sensor_readings_simulator_fallback(self, client, admin_headers):
        self._create_lot("sim_lot")
        payload = {
            "lot_id": "sim_lot",
            "total_slots": 10
        }
        resp = client.post("/api/v1/ingestion/sensor-readings", json=payload, headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ingested"
        assert data["lot_id"] == "sim_lot"
        assert data["fused_count"] == 10
        assert 0.0 <= data["occupancy_rate"] <= 1.0
        assert 0.0 <= data["weather_factor"] <= 1.0

