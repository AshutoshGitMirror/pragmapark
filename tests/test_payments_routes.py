from src.api.database import get_session, ParkingLot


def _create_lot_and_session(client, auth_headers, lot_id="pay_lot"):
    db = get_session()
    try:
        if (
            not db.query(ParkingLot)
            .filter(ParkingLot.lot_id == lot_id)
            .first()
        ):
            db.add(
                ParkingLot(
                    lot_id=lot_id,
                    name="Pay Test",
                    total_slots=100,
                    base_price=10.0,
                    price_cap=50.0,
                )
            )
            db.commit()
    finally:
        db.close()
    start = client.post(
        "/api/v1/sessions/start",
        json={"lot_id": lot_id, "slot": 1},
        headers=auth_headers,
    )
    assert start.status_code == 200
    sid = start.json()["session_id"]
    end = client.post(
        "/api/v1/sessions/end", json={"session_id": sid}, headers=auth_headers
    )
    assert end.status_code == 200, end.text
    return sid


class TestConfirmPayment:
    def test_confirm_requires_auth(self, client):
        resp = client.post(
            "/api/v1/payments/confirm", json={"session_id": "x"}
        )
        assert resp.status_code in (401, 403)

    def test_confirm_returns_404_bad_session(self, client, auth_headers):
        resp = client.post(
            "/api/v1/payments/confirm",
            json={"session_id": "bad"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_confirm_success(self, client, auth_headers):
        sid = _create_lot_and_session(client, auth_headers)
        resp = client.post(
            "/api/v1/payments/confirm",
            json={"session_id": sid},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "tx_hash" in data
        assert data["session_id"] == sid

    def test_confirm_returns_already_paid(self, client, auth_headers):
        sid = _create_lot_and_session(client, auth_headers)
        client.post(
            "/api/v1/payments/confirm",
            json={"session_id": sid},
            headers=auth_headers,
        )
        resp = client.post(
            "/api/v1/payments/confirm",
            json={"session_id": sid},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json().get("already_paid") is True

    def test_confirm_requires_ownership(
        self, client, auth_headers, admin_headers
    ):
        # Clear cookies so _create_lot_and_session uses auth_headers, not admin
        client.cookies.clear()
        sid = _create_lot_and_session(client, auth_headers)
        # Clear cookies again so confirm uses admin_headers, not driver
        client.cookies.clear()
        resp = client.post(
            "/api/v1/payments/confirm",
            json={"session_id": sid},
            headers=admin_headers,
        )
        assert resp.status_code == 403


class TestPaymentHistory:
    def test_history_requires_auth(self, client):
        resp = client.get("/api/v1/payments/history")
        assert resp.status_code in (401, 403)

    def test_history_returns_list(self, client, auth_headers):
        resp = client.get("/api/v1/payments/history", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "payments" in data
        assert "total_payments" in data

    def test_history_shows_paid(self, client, auth_headers):
        sid = _create_lot_and_session(client, auth_headers)
        client.post(
            "/api/v1/payments/confirm",
            json={"session_id": sid},
            headers=auth_headers,
        )
        resp = client.get("/api/v1/payments/history", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["total_payments"] >= 1
