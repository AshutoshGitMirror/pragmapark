from datetime import datetime, timezone, timedelta

_TARGET = (datetime.now(timezone.utc) + timedelta(hours=2)).strftime(
    "%Y-%m-%dT%H:%M:%SZ"
)


class TestPrebookList:
    def test_list_requires_auth(self, client):
        resp = client.get("/api/v1/micro/prebooks/list")
        assert resp.status_code in (401, 403)

    def test_list_returns_empty_when_no_prebooks(self, client, auth_headers):
        resp = client.get("/api/v1/micro/prebooks/list", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        assert "prebooks" in data
        assert data["prebooks"] == []

    def _create_prebook_with(
        self, client, admin_headers, driver_token, lot_id
    ):
        """Seed slots and create a prebook for a driver."""
        client.cookies.clear()
        resp = client.post(
            f"/api/v1/micro/lots/{lot_id}/slots/seed",
            json={"lot_id": lot_id, "count": 10, "slot_type": "regular"},
            headers=admin_headers,
        )
        assert resp.status_code == 200, f"Seed failed: {resp.text}"
        dh = {"Authorization": f"Bearer {driver_token}"}
        client.post("/api/v1/wallet/topup", json={"amount": 100.0}, headers=dh)
        return client.post(
            "/api/v1/micro/prebook",
            json={
                "lot_id": lot_id,
                "slots": [
                    {"slot_index": 1},
                    {"slot_index": 2},
                    {"slot_index": 3},
                ],
                "target_time": _TARGET,
            },
            headers=dh,
        )

    def test_list_returns_prebooks(self, client, admin_headers):
        _ensure_lot("list_lot_2")
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "listdriver@test.com",
                "password": "Pass123!",
                "full_name": "List Driver",
            },
        )
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        self._create_prebook_with(client, admin_headers, token, "list_lot_2")
        resp = client.get(
            "/api/v1/micro/prebooks/list",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["prebooks"]) >= 1
        prebook = data["prebooks"][0]
        assert "prebook_id" in prebook
        assert "lot_id" in prebook
        assert "status" in prebook
        assert "slot_index" in prebook
        assert "target_time" in prebook
        assert "price_at_booking" in prebook

    def test_list_prebook_fields(self, client, admin_headers):
        _ensure_lot("list_lot_3")
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "listdriver2@test.com",
                "password": "Pass123!",
                "full_name": "List Driver 2",
            },
        )
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        self._create_prebook_with(client, admin_headers, token, "list_lot_3")
        resp = client.get(
            "/api/v1/micro/prebooks/list",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        pb = resp.json()["prebooks"][0]
        assert "booking_fee" in pb
        assert "deposit" in pb
        assert "deposit_refunded" in pb
        assert "probability_given" in pb
        assert pb["lot_id"] == "list_lot_3"

    def test_list_scoped_to_driver(self, client, admin_headers):
        _ensure_lot("list_lot_4")
        resp_a = client.post(
            "/api/v1/auth/register",
            json={
                "email": "driver_a@test.com",
                "password": "Pass123!",
                "full_name": "Driver A",
            },
        )
        token_a = resp_a.json()["access_token"]
        resp_b = client.post(
            "/api/v1/auth/register",
            json={
                "email": "driver_b@test.com",
                "password": "Pass123!",
                "full_name": "Driver B",
            },
        )
        token_b = resp_b.json()["access_token"]
        self._create_prebook_with(client, admin_headers, token_a, "list_lot_4")
        resp_b_list = client.get(
            "/api/v1/micro/prebooks/list",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp_b_list.status_code == 200
        assert len(resp_b_list.json()["prebooks"]) == 0


class TestPrebookCancel:
    def test_cancel_requires_auth(self, client):
        resp = client.post(
            "/api/v1/micro/cancel", json={"prebook_id": "nonexistent"}
        )
        assert resp.status_code in (401, 403)

    def test_cancel_nonexistent_returns_404(self, client, auth_headers):
        resp = client.post(
            "/api/v1/micro/cancel",
            json={"prebook_id": "nonexistent_prebook_id"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def _create_prebook_with(
        self, client, admin_headers, driver_token, lot_id
    ):
        client.cookies.clear()
        resp = client.post(
            f"/api/v1/micro/lots/{lot_id}/slots/seed",
            json={"lot_id": lot_id, "count": 10, "slot_type": "regular"},
            headers=admin_headers,
        )
        assert resp.status_code == 200, f"Seed failed: {resp.text}"
        dh = {"Authorization": f"Bearer {driver_token}"}
        client.post("/api/v1/wallet/topup", json={"amount": 100.0}, headers=dh)
        resp = client.post(
            "/api/v1/micro/prebook",
            json={
                "lot_id": lot_id,
                "slots": [
                    {"slot_index": 1},
                    {"slot_index": 2},
                    {"slot_index": 3},
                ],
                "target_time": _TARGET,
            },
            headers=dh,
        )
        assert resp.status_code == 200, f"Prebook failed: {resp.text}"
        return resp.json()

    def test_cancel_active_prebook(self, client, admin_headers):
        _ensure_lot("cancel_lot_1")
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "cancel_driver@test.com",
                "password": "Pass123!",
                "full_name": "Cancel Driver",
            },
        )
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        prebook = self._create_prebook_with(
            client, admin_headers, token, "cancel_lot_1"
        )
        cancel_resp = client.post(
            "/api/v1/micro/cancel",
            json={"prebook_id": prebook["prebook_id"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert cancel_resp.status_code == 200
        data = cancel_resp.json()
        assert data["status"] == "cancelled"
        assert data["prebook_id"] == prebook["prebook_id"]

    def test_cancel_twice_returns_400(self, client, admin_headers):
        _ensure_lot("cancel_lot_2")
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "cancel2@test.com",
                "password": "Pass123!",
                "full_name": "Cancel2 Driver",
            },
        )
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        prebook = self._create_prebook_with(
            client, admin_headers, token, "cancel_lot_2"
        )
        client.post(
            "/api/v1/micro/cancel",
            json={"prebook_id": prebook["prebook_id"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp2 = client.post(
            "/api/v1/micro/cancel",
            json={"prebook_id": prebook["prebook_id"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp2.status_code == 400

    def test_cancel_other_driver_prebook_returns_404(
        self, client, admin_headers
    ):
        _ensure_lot("cancel_lot_3")
        resp_a = client.post(
            "/api/v1/auth/register",
            json={
                "email": "cancel_a@test.com",
                "password": "Pass123!",
                "full_name": "Cancel A",
            },
        )
        token_a = resp_a.json()["access_token"]
        prebook = self._create_prebook_with(
            client, admin_headers, token_a, "cancel_lot_3"
        )
        resp_b = client.post(
            "/api/v1/auth/register",
            json={
                "email": "cancel_b@test.com",
                "password": "Pass123!",
                "full_name": "Cancel B",
            },
        )
        token_b = resp_b.json()["access_token"]
        cancel_resp = client.post(
            "/api/v1/micro/cancel",
            json={"prebook_id": prebook["prebook_id"]},
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert cancel_resp.status_code == 404


def _ensure_lot(lot_id):
    """Create a ParkingLot directly in the DB if it doesn't exist."""
    from sqlalchemy import select
    from src.api.database import get_session, ParkingLot

    db = get_session()
    try:
        if (
            not db.execute(
                select(ParkingLot).where(ParkingLot.lot_id == lot_id)
            )
            .scalars()
            .first()
        ):
            db.add(
                ParkingLot(
                    lot_id=lot_id,
                    name=f"Test {lot_id}",
                    total_slots=50,
                    base_price=5.0,
                    price_cap=20.0,
                )
            )
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
