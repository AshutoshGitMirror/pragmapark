from sqlalchemy import select
from src.api.database import get_session, ParkingLot, User
from src.api.auth import hash_password


class TestLotsOwner:
    def _create_lot_with_owner(self, client, email, role="lot_owner"):
        db = get_session()
        try:
            user = (
                db.execute(select(User).where(User.email == email))
                .scalars()
                .first()
            )
            if not user:
                user = User(
                    email=email,
                    hashed_password=hash_password("Pass123!"),
                    full_name="Owner",
                    role=role,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
        finally:
            db.close()
        resp = client.post(
            "/api/v1/auth/login", json={"email": email, "password": "Pass123!"}
        )
        assert resp.status_code == 200, (
            f"Login failed for {email}: {resp.text}"
        )
        token = resp.json().get("access_token", "")
        headers = {"Authorization": f"Bearer {token}"}
        # Create a lot
        client.post(
            "/api/v1/lots",
            json={
                "lot_id": f"{email.split('@')[0]}_lot",
                "name": f"{email.split('@')[0]} Lot",
                "total_slots": 50,
                "base_price": 5.0,
                "price_cap": 20.0,
            },
            headers=headers,
        )
        return headers

    def test_owner_lots_requires_auth(self, client):
        resp = client.get("/api/v1/lots/owner")
        assert resp.status_code in (401, 403)

    def test_owner_lots_returns_user_lots(self, client):
        headers = self._create_lot_with_owner(client, "owner1@test.com")
        resp = client.get("/api/v1/lots/owner", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert data[0]["lot_id"] == "owner1_lot"

    def test_owner_lots_admin_sees_all(self, client, admin_headers):
        self._create_lot_with_owner(client, "owner2@test.com")
        resp = client.get("/api/v1/lots/owner", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        lot_ids = [lot["lot_id"] for lot in data]
        assert "owner2_lot" in lot_ids

    def test_owner_lots_returns_summaries(self, client):
        headers = self._create_lot_with_owner(client, "owner3@test.com")
        resp = client.get("/api/v1/lots/owner", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        item = data[0]
        assert "lot_id" in item
        assert "name" in item
        assert "total_slots" in item
        assert "base_price" in item
        assert "current_occupancy" in item

    def test_owner_lots_pagination(self, client, admin_headers):
        resp = client.get(
            "/api/v1/lots/owner?offset=0&limit=5", headers=admin_headers
        )
        assert resp.status_code == 200
        assert len(resp.json()) <= 5


class TestLotsUpdateConfig:
    def test_update_config_requires_auth(self, client):
        resp = client.put(
            "/api/v1/lots/test_lot/config", json={"base_price": 8.0}
        )
        assert resp.status_code in (401, 403)

    def test_update_config_updates_price(self, client, admin_headers):
        # Create lot first
        client.post(
            "/api/v1/lots",
            json={
                "lot_id": "update_price_lot",
                "name": "Update Price Lot",
                "total_slots": 30,
                "base_price": 5.0,
                "price_cap": 25.0,
            },
            headers=admin_headers,
        )
        resp = client.put(
            "/api/v1/lots/update_price_lot/config",
            json={"base_price": 8.0, "price_cap": 30.0},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "updated"
        assert data["base_price"] == 8.0
        assert data["price_cap"] == 30.0

    def test_update_nonexistent_lot_returns_404(self, client, admin_headers):
        resp = client.put(
            "/api/v1/lots/nonexistent_lot_id/config",
            json={"base_price": 8.0},
            headers=admin_headers,
        )
        assert resp.status_code == 404

    def test_update_config_updates_name_and_address(
        self, client, admin_headers
    ):
        client.post(
            "/api/v1/lots",
            json={
                "lot_id": "update_name_lot",
                "name": "Original Name",
                "total_slots": 20,
                "base_price": 4.0,
                "price_cap": 15.0,
            },
            headers=admin_headers,
        )
        resp = client.put(
            "/api/v1/lots/update_name_lot/config",
            json={"name": "Updated Name", "address": "123 New St"},
            headers=admin_headers,
        )
        assert resp.status_code == 200

    def test_update_config_persists_in_db(self, client, admin_headers):
        client.post(
            "/api/v1/lots",
            json={
                "lot_id": "persist_lot",
                "name": "Persist Lot",
                "total_slots": 40,
                "base_price": 3.0,
                "price_cap": 12.0,
            },
            headers=admin_headers,
        )
        client.put(
            "/api/v1/lots/persist_lot/config",
            json={"total_slots": 50},
            headers=admin_headers,
        )
        db = get_session()
        try:
            lot = (
                db.execute(
                    select(ParkingLot).where(
                        ParkingLot.lot_id == "persist_lot"
                    )
                )
                .scalars()
                .first()
            )
            assert lot is not None
            assert lot.total_slots == 50
        finally:
            db.close()


def _ensure_lot(lot_id: str):
    """Create a ParkingLot directly in the DB if it doesn't exist."""
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
    finally:
        db.close()


class TestLotsOccupancy:
    def test_occupancy_no_auth_required(self, client):
        _ensure_lot("occ_lot_1")
        resp = client.get("/api/v1/lots/occ_lot_1/occupancy")
        assert resp.status_code == 200

    def test_occupancy_returns_lot_info(self, client):
        _ensure_lot("occ_lot_2")
        resp = client.get("/api/v1/lots/occ_lot_2/occupancy")
        assert resp.status_code == 200
        data = resp.json()
        assert data["lot_id"] == "occ_lot_2"
        assert "name" in data
        assert "current_occupancy" in data
        assert "current_price" in data
        assert "records" in data

    def test_occupancy_nonexistent_lot_returns_404(self, client):
        resp = client.get("/api/v1/lots/bad_lot_name/occupancy")
        assert resp.status_code == 404

    def test_occupancy_hours_param(self, client):
        _ensure_lot("occ_lot_3")
        resp = client.get("/api/v1/lots/occ_lot_3/occupancy?hours=1")
        assert resp.status_code == 200

    def test_occupancy_matches_pydantic_schema(self, client):
        _ensure_lot("occ_lot_4")
        resp = client.get("/api/v1/lots/occ_lot_4/occupancy")
        assert resp.status_code == 200
        from src.api.schemas import LotOccupancyResponse

        validated = LotOccupancyResponse(**resp.json())
        assert validated.lot_id == "occ_lot_4"
