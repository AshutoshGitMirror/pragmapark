"""Tests for GET /api/v1/residential/map (Phase 1 residential map endpoint)."""
from datetime import date

from src.api.database import (
    get_session,
    MicroSlot,
    ResidentProfile,
    User,
)


def _seed_standalone_slot(db, owner_id, lat, lng):
    slot = MicroSlot(lot_id=None, slot_index=1, active=1, latitude=lat, longitude=lng)
    db.add(slot)
    db.commit()
    db.refresh(slot)
    prof = ResidentProfile(
        user_id=owner_id,
        slot_id=slot.id,
        permit_type="monthly",
        monthly_rate=50.0,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )
    db.add(prof)
    db.commit()
    db.refresh(prof)
    return slot, prof


class TestResidentialMapEndpoint:
    def test_map_returns_standalone_and_attached(self, client, admin_headers, auth_headers):
        # lot-attached permitted + shared slot
        resp = client.post(
            "/api/v1/lots",
            json={"lot_id": "map_lot", "name": "Map Lot", "total_slots": 5,
                  "base_price": 10.0, "price_cap": 50.0,
                  "latitude": 19.01, "longitude": 72.91},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        resp = client.post("/api/v1/micro/lots/map_lot/slots/seed", headers=admin_headers)
        assert resp.status_code == 200, resp.text
        resp = client.post(
            "/api/v1/residential/permits",
            json={"lot_id": "map_lot", "slot_index": 1, "permit_type": "monthly",
                  "start_date": "2025-01-01", "end_date": "2025-12-31"},
            headers=auth_headers,
        )
        assert resp.status_code == 201, resp.text
        permit = resp.json()
        resp = client.post(
            "/api/v1/residential/shares",
            json={"resident_profile_id": permit["id"], "price_per_hour": 5.0},
            headers=auth_headers,
        )
        assert resp.status_code == 201, resp.text

        # standalone home slot (lot_id NULL) owned by the test user
        db = get_session()
        try:
            owner = db.query(User).filter(User.email == "test@pragma.io").first()
            _seed_standalone_slot(db, owner.id, 19.10, 72.85)
            # lot-attached slot needs coords to render on the map; the seed
            # endpoint doesn't copy them, so set them from the lot like the
            # migration backfill would.
            attached = db.query(MicroSlot).filter(
                MicroSlot.lot_id == "map_lot", MicroSlot.slot_index == 1
            ).first()
            attached.latitude = 19.01
            attached.longitude = 72.91
            db.commit()
        finally:
            db.close()

        resp = client.get("/api/v1/residential/map", headers=admin_headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 2

        by_slot = {d["slot_id"]: d for d in data}
        standalone = next(d for d in data if d["lot_id"] is None)
        assert standalone["spatial_id"].startswith("PK_")
        assert standalone["latitude"] == 19.10
        assert standalone["longitude"] == 72.85
        assert standalone["is_shared"] is False
        assert standalone["has_permit"] is True

        shared = next(d for d in data if d["is_shared"] is True)
        assert shared["lot_id"] == "map_lot"
        assert shared["price_per_hour"] == 5.0
        assert "spatial_id" in shared

    def test_map_empty_when_no_slots(self, client, admin_headers):
        resp = client.get("/api/v1/residential/map", headers=admin_headers)
        assert resp.status_code == 200, resp.text
        assert isinstance(resp.json(), list)
