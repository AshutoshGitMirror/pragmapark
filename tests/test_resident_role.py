"""Tests for the distinct resident role and permit/share flow (Resident UI backend)."""
from datetime import date

from src.api.auth import hash_password
from src.api.database import get_session, MicroSlot, ResidentProfile, User


def _make_resident(client, db, email="resident_test@pragma.io", password="ResidentPass123!"):
    u = db.query(User).filter(User.email == email).first()
    if u is None:
        u = User(
            email=email,
            hashed_password=hash_password(password),
            full_name="Resident Tester",
            role="resident",
            organization="",
        )
        db.add(u)
        db.commit()
        db.refresh(u)
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"], u


class TestResidentRole:
    def test_resident_role_persists_and_auth_me(self, client):
        db = get_session()
        try:
            token, user = _make_resident(client, db)
        finally:
            db.close()
        headers = {"Authorization": f"Bearer {token}"}
        resp = client.get("/api/v1/auth/me", headers=headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["role"] == "resident"

    def test_resident_manages_own_permit_and_share(self, client, admin_headers):
        # Admin provisions a lot + slot for the resident to attach a permit to.
        resp = client.post(
            "/api/v1/lots",
            json={"lot_id": "res_lot", "name": "Res Lot", "total_slots": 3,
                  "base_price": 10.0, "price_cap": 50.0,
                  "latitude": 19.02, "longitude": 72.92},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        resp = client.post(
            "/api/v1/micro/lots/res_lot/slots/seed", headers=admin_headers
        )
        assert resp.status_code == 200, resp.text

        # Distinct resident user authenticates.
        db = get_session()
        try:
            token, _ = _make_resident(client, db)
        finally:
            db.close()
        headers = {"Authorization": f"Bearer {token}"}

        # Resident creates a permit on the lot-attached home slot.
        resp = client.post(
            "/api/v1/residential/permits",
            json={"lot_id": "res_lot", "slot_index": 1, "permit_type": "monthly",
                  "start_date": "2025-01-01", "end_date": "2025-12-31"},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        permit = resp.json()
        assert permit["user_email"] == "resident_test@pragma.io"
        assert permit["lot_id"] == "res_lot"

        # Resident lists their permit.
        resp = client.get("/api/v1/residential/permits", headers=headers)
        assert resp.status_code == 200, resp.text
        assert any(p["id"] == permit["id"] for p in resp.json())

        # Resident shares the slot.
        resp = client.post(
            "/api/v1/residential/shares",
            json={"resident_profile_id": permit["id"], "price_per_hour": 40.0,
                  "available_from": "09:00", "available_until": "18:00"},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        listing = resp.json()
        assert listing["status"] == "active"

        # Resident sees the share in their listings.
        resp = client.get("/api/v1/residential/shares", headers=headers)
        assert resp.status_code == 200, resp.text
        assert any(s["id"] == listing["id"] for s in resp.json())

        # Resident stops sharing.
        resp = client.delete(f"/api/v1/residential/shares/{listing['id']}", headers=headers)
        assert resp.status_code == 200, resp.text
        resp = client.get("/api/v1/residential/shares", headers=headers)
        remaining = [s for s in resp.json() if s["id"] == listing["id"]]
        assert remaining == [] or remaining[0]["status"] != "active"


class TestSeedResidentUser:
    def test_seed_resident_user_idempotent(self, client):
        from src.api.server import _seed_resident_user

        _seed_resident_user()
        db = get_session()
        try:
            u = db.query(User).filter(User.email == "resident@pragma.io").first()
            assert u is not None
            assert u.role == "resident"
            prof = db.query(ResidentProfile).filter(
                ResidentProfile.user_id == u.id
            ).first()
            assert prof is not None
            slot = db.query(MicroSlot).filter(MicroSlot.id == prof.slot_id).first()
            assert slot is not None

            # Second run must not duplicate the user or permit.
            _seed_resident_user()
            users = db.query(User).filter(User.email == "resident@pragma.io").all()
            assert len(users) == 1
            profiles = db.query(ResidentProfile).filter(
                ResidentProfile.user_id == u.id
            ).all()
            assert len(profiles) == 1
        finally:
            db.close()
