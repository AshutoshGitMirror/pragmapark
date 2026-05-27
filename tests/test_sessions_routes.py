from src.api.database import get_session, ParkingLot


def _create_lot(lot_id="sess_lot"):
    db = get_session()
    try:
        if not db.query(ParkingLot).filter(ParkingLot.lot_id == lot_id).first():
            db.add(ParkingLot(lot_id=lot_id, name="Sess Test", total_slots=100, base_price=10.0, price_cap=50.0))
            db.commit()
    finally:
        db.close()


class TestStartSession:
    def test_start_requires_auth(self, client):
        resp = client.post("/api/v1/sessions/start", json={"lot_id": "x", "slot": 1})
        assert resp.status_code in (401, 403)

    def test_start_returns_409_bad_lot(self, client, auth_headers):
        resp = client.post("/api/v1/sessions/start", json={"lot_id": "nonexistent", "slot": 1}, headers=auth_headers)
        assert resp.status_code == 409

    def test_start_success(self, client, auth_headers):
        _create_lot()
        resp = client.post("/api/v1/sessions/start", json={"lot_id": "sess_lot", "slot": 1}, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert data["lot_id"] == "sess_lot"
        assert "price_at_entry" in data


class TestEndSession:
    def test_end_requires_auth(self, client):
        resp = client.post("/api/v1/sessions/end", json={"session_id": "x"})
        assert resp.status_code in (401, 403)

    def test_end_returns_404_bad_session(self, client, auth_headers):
        resp = client.post("/api/v1/sessions/end", json={"session_id": "bad_sess"}, headers=auth_headers)
        assert resp.status_code == 404

    def test_end_full_flow(self, client, auth_headers):
        _create_lot()
        start = client.post("/api/v1/sessions/start", json={"lot_id": "sess_lot", "slot": 1}, headers=auth_headers)
        assert start.status_code == 200
        sid = start.json()["session_id"]
        resp = client.post("/api/v1/sessions/end", json={"session_id": sid}, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == sid
        assert "amount_charged" in data

    def test_end_requires_ownership(self, client, auth_headers, admin_headers):
        _create_lot()
        start = client.post("/api/v1/sessions/start", json={"lot_id": "sess_lot", "slot": 1}, headers=auth_headers)
        sid = start.json()["session_id"]
        resp = client.post("/api/v1/sessions/end", json={"session_id": sid}, headers=admin_headers)
        assert resp.status_code == 403


class TestActiveSessions:
    def test_active_requires_auth(self, client):
        resp = client.get("/api/v1/sessions/active/sess_lot")
        assert resp.status_code in (401, 403)

    def test_active_returns_empty_for_unknown_lot(self, client, auth_headers):
        resp = client.get("/api/v1/sessions/active/unknown_lot", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["active_count"] == 0


class TestHistory:
    def test_history_requires_auth(self, client):
        resp = client.get("/api/v1/sessions/history")
        assert resp.status_code in (401, 403)

    def test_history_returns_list(self, client, auth_headers):
        resp = client.get("/api/v1/sessions/history", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data
        assert "total_sessions" in data


class TestSessionDetail:
    def test_detail_requires_auth(self, client):
        resp = client.get("/api/v1/sessions/bad")
        assert resp.status_code in (401, 403)

    def test_detail_returns_404(self, client, auth_headers):
        resp = client.get("/api/v1/sessions/bad_sess", headers=auth_headers)
        assert resp.status_code == 404

    def test_detail_shows_own_session(self, client, auth_headers):
        _create_lot()
        start = client.post("/api/v1/sessions/start", json={"lot_id": "sess_lot", "slot": 1}, headers=auth_headers)
        sid = start.json()["session_id"]
        resp = client.get(f"/api/v1/sessions/{sid}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["session_id"] == sid


class TestPricingBreakdown:
    def test_breakdown_requires_auth(self, client):
        resp = client.get("/api/v1/sessions/bad/pricing")
        assert resp.status_code in (401, 403)

    def test_breakdown_returns_404(self, client, auth_headers):
        resp = client.get("/api/v1/sessions/bad/pricing", headers=auth_headers)
        assert resp.status_code == 404

    def test_breakdown_full(self, client, auth_headers):
        _create_lot()
        start = client.post("/api/v1/sessions/start", json={"lot_id": "sess_lot", "slot": 1}, headers=auth_headers)
        sid = start.json()["session_id"]
        resp = client.get(f"/api/v1/sessions/{sid}/pricing", headers=auth_headers)
        assert resp.status_code == 200
        assert "entry_price" in resp.json()


class TestReceipt:
    def test_receipt_requires_auth(self, client):
        resp = client.get("/api/v1/sessions/bad/receipt")
        assert resp.status_code in (401, 403)

    def test_receipt_returns_404(self, client, auth_headers):
        resp = client.get("/api/v1/sessions/bad/receipt", headers=auth_headers)
        assert resp.status_code == 404
