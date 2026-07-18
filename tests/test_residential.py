import pytest
import re
from datetime import datetime, timezone, timedelta

from src.api.database import get_session, MicroSlot, ResidentProfile, ShareListing, ShareBooking
from src.constants import (
    SHARE_LISTING_ACTIVE, SHARE_LISTING_BOOKED, SHARE_LISTING_CANCELLED,
    SHARE_BOOKING_ACTIVE, SHARE_BOOKING_COMPLETED, SHARE_BOOKING_CANCELLED,
    SHARE_PLATFORM_FEE, PERMIT_MONTHLY, PERMIT_RATES, VEHICLE_ID_PATTERN,
    TX_ACTION_SHARE_BOOKING, TX_ACTION_SHARE_SETTLEMENT, TX_ACTION_SHARE_CANCELLATION,
    RL_DEFAULT_RESIDENT_RATIO,
)
from src.micro.resident_map import slot_resident_mapping
from src.pipeline.orchestrator import pipeline


def _ensure_user(client, email, password, full_name="Alt Driver"):
    """Register (unique email to avoid stale-user collisions) then login; return Bearer token."""
    import uuid
    unique_email = f"{email.split('@')[0]}.{uuid.uuid4().hex[:8]}@pragma.io"
    client.post("/api/v1/auth/register", json={
        "email": unique_email, "password": password, "full_name": full_name,
    })
    login = client.post("/api/v1/auth/login", json={
        "email": unique_email, "password": password,
    })
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def _future(hours_ahead=2):
    now = datetime.now(timezone.utc)
    if hours_ahead < 0:
        return now + timedelta(hours=hours_ahead)  # genuinely in the past
    # Land mid-window (12:00 UTC + offset) so bookings stay inside any
    # listing's daily availability window (e.g. 06:00-22:00) regardless of
    # the wall-clock hour CI happens to run at.
    start = now.replace(hour=12, minute=0, second=0, microsecond=0) + timedelta(
        hours=hours_ahead
    )
    if start <= now:
        start += timedelta(days=1)
    return start


class TestResidentialConstantsAndModels:

    def test_constants_exist_and_have_correct_values(self):
        assert SHARE_LISTING_ACTIVE == "active"
        assert SHARE_LISTING_BOOKED == "booked"
        assert SHARE_LISTING_CANCELLED == "cancelled"
        assert SHARE_BOOKING_ACTIVE == "active"
        assert SHARE_BOOKING_COMPLETED == "completed"
        assert SHARE_BOOKING_CANCELLED == "cancelled"
        assert SHARE_PLATFORM_FEE == 0.10
        assert PERMIT_MONTHLY == "monthly"
        assert PERMIT_RATES == {"monthly": 50.0}
        assert VEHICLE_ID_PATTERN == r"^[A-Z]{2}[0-9]{2}[A-Z]{0,2}[0-9]{1,4}$"
        assert TX_ACTION_SHARE_BOOKING == "share_booking"
        assert TX_ACTION_SHARE_SETTLEMENT == "share_settlement"
        assert TX_ACTION_SHARE_CANCELLATION == "share_cancellation"
        assert RL_DEFAULT_RESIDENT_RATIO == 0.0

    def test_resident_profile_create_and_unique_constraint(self, client, admin_headers, auth_headers):
        resp = client.post("/api/v1/lots", json={
            "lot_id": "ct_lot", "name": "CT Lot",
            "total_slots": 10, "base_price": 10.0, "price_cap": 50.0,
        }, headers=admin_headers)
        assert resp.status_code == 200, resp.text

        resp = client.post("/api/v1/micro/lots/ct_lot/slots/seed", headers=admin_headers)
        assert resp.status_code == 200, resp.text

        resp = client.post("/api/v1/residential/permits", json={
            "lot_id": "ct_lot", "slot_index": 1, "permit_type": "monthly",
            "start_date": "2025-01-01", "end_date": "2025-12-31",
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["lot_id"] == "ct_lot"
        assert data["slot_index"] == 1
        assert data["permit_type"] == "monthly"
        assert data["start_date"] == "2025-01-01"
        assert data["end_date"] == "2025-12-31"
        assert data["monthly_rate"] == 50.0
        assert data["is_active"] == True
        assert data["auto_renew"] == True
        assert data["registered_vehicle"] is None
        assert data["user_email"] == "test@pragma.io"
        assert isinstance(data["id"], int) and data["id"] >= 1
        assert isinstance(data["user_id"], int) and data["user_id"] >= 1
        assert isinstance(data["lot_name"], str) and len(data["lot_name"]) > 0
        assert isinstance(data["created_at"], str) and len(data["created_at"]) > 0
        assert isinstance(data["updated_at"], str) and len(data["updated_at"]) > 0

        resp2 = client.post("/api/v1/residential/permits", json={
            "lot_id": "ct_lot", "slot_index": 1, "permit_type": "monthly",
            "start_date": "2025-01-01", "end_date": "2025-12-31",
        }, headers=auth_headers)
        assert resp2.status_code == 409, resp2.text
        assert resp2.json()["detail"] == "Slot already has an active permit"

        db = get_session()
        try:
            slot = db.query(MicroSlot).filter(
                MicroSlot.lot_id == "ct_lot", MicroSlot.slot_index == 1
            ).first()
            assert slot is not None
            profiles = db.query(ResidentProfile).filter(
                ResidentProfile.slot_id == slot.id
            ).all()
            assert len(profiles) == 1
        finally:
            db.close()

    def test_share_listing_and_booking_model_create(self, client, admin_headers, auth_headers):
        resp = client.post("/api/v1/lots", json={
            "lot_id": "ct_lot2", "name": "CT Lot 2",
            "total_slots": 10, "base_price": 10.0, "price_cap": 50.0,
        }, headers=admin_headers)
        assert resp.status_code == 200, resp.text

        resp = client.post("/api/v1/micro/lots/ct_lot2/slots/seed", headers=admin_headers)
        assert resp.status_code == 200, resp.text

        resp = client.post("/api/v1/residential/permits", json={
            "lot_id": "ct_lot2", "slot_index": 1, "permit_type": "monthly",
            "start_date": "2025-01-01", "end_date": "2025-12-31",
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        permit = resp.json()

        resp = client.post("/api/v1/residential/shares", json={
            "resident_profile_id": permit["id"], "price_per_hour": 5.0,
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        listing = resp.json()
        assert listing["status"] == "active"
        assert listing["price_per_hour"] == 5.0
        assert listing["available_from"] == "00:00"
        assert listing["available_until"] == "23:59"
        assert listing["max_advance_days"] == 7
        assert listing["resident_profile_id"] == permit["id"]
        assert listing["slot_index"] == 1

        start = datetime.now(timezone.utc) + timedelta(hours=2)
        end = start + timedelta(hours=3)
        resp = client.post("/api/v1/residential/shares/book", json={
            "share_listing_id": listing["id"],
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        booking = resp.json()
        assert booking["status"] == "active"
        assert booking["share_listing_id"] == listing["id"]
        total = round(3 * 5.0, 2)
        fee = round(total * 0.10, 2)
        payout = round(total - fee, 2)
        assert booking["total_cost"] == total
        assert booking["platform_fee"] == fee
        assert booking["owner_payout"] == payout

    def test_vehicle_id_pattern_validation(self, client, admin_headers, auth_headers):
        resp = client.post("/api/v1/lots", json={
            "lot_id": "ct_lot3", "name": "CT Lot 3",
            "total_slots": 10, "base_price": 10.0, "price_cap": 50.0,
        }, headers=admin_headers)
        assert resp.status_code == 200, resp.text
        resp = client.post("/api/v1/micro/lots/ct_lot3/slots/seed", headers=admin_headers)
        assert resp.status_code == 200, resp.text
        resp = client.post("/api/v1/residential/permits", json={
            "lot_id": "ct_lot3", "slot_index": 1, "permit_type": "monthly",
            "start_date": "2025-01-01", "end_date": "2025-12-31",
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        permit = resp.json()

        resp = client.put(f"/api/v1/residential/permits/{permit['id']}/vehicle", json={
            "vehicle_id": "MH12AB1234",
        }, headers=auth_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["registered_vehicle"] == "MH12AB1234"

        resp = client.put(f"/api/v1/residential/permits/{permit['id']}/vehicle", json={
            "vehicle_id": "invalid",
        }, headers=auth_headers)
        assert resp.status_code == 422, resp.text

        resp = client.put(f"/api/v1/residential/permits/{permit['id']}/vehicle", json={
            "vehicle_id": "",
        }, headers=auth_headers)
        assert resp.status_code == 422, resp.text

        resp = client.put(f"/api/v1/residential/permits/{permit['id']}/vehicle", json={
            "vehicle_id": "ABC123",
        }, headers=auth_headers)
        assert resp.status_code == 422, resp.text

    def test_vehicle_id_regex_matches_source(self):
        pattern = re.compile(VEHICLE_ID_PATTERN)
        assert pattern.match("MH12AB1234")
        assert pattern.match("DL01C5678")
        assert pattern.match("KA05D1234")
        assert not pattern.match("invalid")
        assert not pattern.match("")
        assert not pattern.match("ABC123")
        assert not pattern.match("MH12AB12345")
        assert not pattern.match("MH12AB")


class TestResidentialAPI:

    @pytest.fixture
    def seeded_lot(self, client, admin_headers):
        resp = client.post("/api/v1/lots", json={
            "lot_id": "res_api_lot", "name": "Res API Lot",
            "total_slots": 10, "base_price": 10.0, "price_cap": 50.0,
        }, headers=admin_headers)
        assert resp.status_code == 200, resp.text
        resp = client.post("/api/v1/micro/lots/res_api_lot/slots/seed", headers=admin_headers)
        assert resp.status_code == 200, resp.text
        return "res_api_lot"

    @pytest.fixture
    def resident_permit(self, client, auth_headers, seeded_lot):
        resp = client.post("/api/v1/residential/permits", json={
            "lot_id": seeded_lot, "slot_index": 1, "permit_type": "monthly",
            "start_date": "2025-01-01", "end_date": "2025-12-31",
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        return resp.json()

    @pytest.fixture
    def share_listing(self, client, auth_headers, resident_permit):
        resp = client.post("/api/v1/residential/shares", json={
            "resident_profile_id": resident_permit["id"],
            "price_per_hour": 5.0,
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        return resp.json()

    @pytest.fixture
    def alt_auth_headers(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "email": "alt_res@pragma.io", "password": "AltPass123!",
            "full_name": "Alt Resident",
        })
        assert resp.status_code == 200, resp.text
        token = resp.json().get("access_token", "")
        return {"Authorization": f"Bearer {token}"}



    # ── POST /permits ───────────────────────────────────────────────────────

    def test_create_permit_success(self, client, auth_headers, seeded_lot):
        resp = client.post("/api/v1/residential/permits", json={
            "lot_id": seeded_lot, "slot_index": 2, "permit_type": "monthly",
            "start_date": "2025-06-01", "end_date": "2026-05-31",
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        d = resp.json()
        assert d["lot_id"] == seeded_lot
        assert d["slot_index"] == 2
        assert d["permit_type"] == "monthly"
        assert d["start_date"] == "2025-06-01"
        assert d["end_date"] == "2026-05-31"
        assert d["monthly_rate"] == 50.0
        assert d["is_active"] is True
        assert d["auto_renew"] is True
        assert d["registered_vehicle"] is None
        assert d["user_email"] == "test@pragma.io"
        assert isinstance(d["id"], int) and d["id"] >= 1
        assert isinstance(d["user_id"], int) and d["user_id"] >= 1
        assert d["lot_name"] == "Res API Lot"
        assert isinstance(d["created_at"], str) and len(d["created_at"]) > 0
        assert isinstance(d["updated_at"], str) and len(d["updated_at"]) > 0

    def test_create_permit_duplicate_slot(self, client, auth_headers, resident_permit):
        resp = client.post("/api/v1/residential/permits", json={
            "lot_id": resident_permit["lot_id"], "slot_index": 1,
            "permit_type": "monthly",
            "start_date": "2025-01-01", "end_date": "2025-12-31",
        }, headers=auth_headers)
        assert resp.status_code == 409, resp.text
        assert resp.json()["detail"] == "Slot already has an active permit"

    def test_create_permit_deactivated_slot_reactivate(self, client, auth_headers, seeded_lot):
        resp = client.post("/api/v1/residential/permits", json={
            "lot_id": seeded_lot, "slot_index": 3, "permit_type": "monthly",
            "start_date": "2025-01-01", "end_date": "2025-12-31",
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        pid = resp.json()["id"]

        resp = client.post(f"/api/v1/residential/permits/{pid}/deactivate", headers=auth_headers)
        assert resp.status_code == 200, resp.text

        resp = client.post("/api/v1/residential/permits", json={
            "lot_id": seeded_lot, "slot_index": 3, "permit_type": "monthly",
            "start_date": "2025-01-01", "end_date": "2025-12-31",
        }, headers=auth_headers)
        assert resp.status_code == 409, resp.text
        assert resp.json()["detail"] == (
            "A deactivated permit exists for this slot. "
            "Reactivate the existing permit instead."
        )

    def test_create_permit_invalid_type(self, client, auth_headers, seeded_lot):
        resp = client.post("/api/v1/residential/permits", json={
            "lot_id": seeded_lot, "slot_index": 4, "permit_type": "invalid",
            "start_date": "2025-01-01", "end_date": "2025-12-31",
        }, headers=auth_headers)
        assert resp.status_code == 422, resp.text

    def test_create_permit_past_date(self, client, auth_headers, seeded_lot):
        resp = client.post("/api/v1/residential/permits", json={
            "lot_id": seeded_lot, "slot_index": 5, "permit_type": "monthly",
            "start_date": "2024-01-01", "end_date": "2024-01-01",
        }, headers=auth_headers)
        assert resp.status_code == 400, resp.text
        assert resp.json()["detail"] == "end_date must be after start_date"

    def test_create_permit_invalid_slot(self, client, auth_headers, seeded_lot):
        resp = client.post("/api/v1/residential/permits", json={
            "lot_id": seeded_lot, "slot_index": 999, "permit_type": "monthly",
            "start_date": "2025-01-01", "end_date": "2025-12-31",
        }, headers=auth_headers)
        assert resp.status_code == 404, resp.text
        assert resp.json()["detail"] == f"Slot {seeded_lot}/999 not found or inactive"

    # ── GET /permits ────────────────────────────────────────────────────────

    def test_list_permits(self, client, auth_headers, resident_permit):
        resp = client.get("/api/v1/residential/permits", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        entry = next(e for e in data if e["slot_index"] == 1)
        assert entry["lot_id"] == resident_permit["lot_id"]
        assert entry["permit_type"] == "monthly"
        assert entry["is_active"] is True

    def test_list_permits_empty(self, client, alt_auth_headers):
        resp = client.get("/api/v1/residential/permits", headers=alt_auth_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json() == []

    # ── GET /permits/{lot_id}/slots ──────────────────────────────────────────

    def test_list_permit_slots(self, client, auth_headers, resident_permit):
        resp = client.get(
            f"/api/v1/residential/permits/{resident_permit['lot_id']}/slots",
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        entry = next(e for e in data if e["slot_index"] == 1)
        assert entry["permit_type"] == "monthly"
        assert entry["is_active"] is True
        assert entry["registered_vehicle"] is None

    # ── POST /shares ────────────────────────────────────────────────────────

    def test_create_share_listing_success(self, client, auth_headers, resident_permit):
        resp = client.post("/api/v1/residential/shares", json={
            "resident_profile_id": resident_permit["id"],
            "price_per_hour": 5.0,
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        d = resp.json()
        assert d["status"] == "active"
        assert d["price_per_hour"] == 5.0
        assert d["available_from"] == "00:00"
        assert d["available_until"] == "23:59"
        assert d["max_advance_days"] == 7
        assert d["resident_profile_id"] == resident_permit["id"]
        assert d["resident_name"] == "Test User"
        assert d["lot_id"] == resident_permit["lot_id"]
        assert d["lot_name"] == "Res API Lot"
        assert d["slot_index"] == 1
        assert d["registered_vehicle"] is None
        assert isinstance(d["id"], int) and d["id"] >= 1
        assert isinstance(d["created_at"], str) and len(d["created_at"]) > 0
        assert isinstance(d["updated_at"], str) and len(d["updated_at"]) > 0

    def test_create_share_listing_duplicate(self, client, auth_headers, share_listing, resident_permit):
        resp = client.post("/api/v1/residential/shares", json={
            "resident_profile_id": resident_permit["id"],
            "price_per_hour": 5.0,
        }, headers=auth_headers)
        assert resp.status_code == 409, resp.text
        assert resp.json()["detail"] == "An active share listing already exists for this slot"

    def test_create_share_listing_no_permit(self, client, auth_headers):
        resp = client.post("/api/v1/residential/shares", json={
            "resident_profile_id": 99999, "price_per_hour": 5.0,
        }, headers=auth_headers)
        assert resp.status_code == 404, resp.text
        assert resp.json()["detail"] == "Resident profile not found"

    def test_create_share_listing_lot_slot_ref(self, client, auth_headers, resident_permit):
        resp = client.post("/api/v1/residential/shares", json={
            "lot_id": resident_permit["lot_id"], "slot_index": resident_permit["slot_index"],
            "price_per_hour": 5.0,
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text

    def test_create_share_listing_no_ref(self, client, auth_headers):
        resp = client.post("/api/v1/residential/shares", json={
            "price_per_hour": 5.0,
        }, headers=auth_headers)
        assert resp.status_code == 400, resp.text
        assert resp.json()["detail"] == "Provide resident_profile_id or lot_id+slot_index"

    # ── GET /shares ─────────────────────────────────────────────────────────

    def test_browse_shares(self, client, auth_headers, share_listing):
        resp = client.get("/api/v1/residential/shares", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert isinstance(data, list)
        assert any(s["id"] == share_listing["id"] and s["status"] == "active" for s in data)

    def test_browse_shares_empty(self, client, alt_auth_headers):
        resp = client.get("/api/v1/residential/shares", headers=alt_auth_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json() == []

    # ── POST /shares/book ───────────────────────────────────────────────────

    def test_book_share_success(self, client, auth_headers, share_listing):
        start = _future(2)
        end = start + timedelta(hours=3)
        resp = client.post("/api/v1/residential/shares/book", json={
            "share_listing_id": share_listing["id"],
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        d = resp.json()
        assert d["status"] == "active"
        assert d["share_listing_id"] == share_listing["id"]
        total = round(3 * 5.0, 2)
        fee = round(total * 0.10, 2)
        payout = round(total - fee, 2)
        assert d["total_cost"] == total
        assert d["platform_fee"] == fee
        assert d["owner_payout"] == payout
        assert d["driver_name"] == "Test User"
        assert d["lot_name"] == "Res API Lot"
        assert d["slot_index"] == 1
        assert d["vehicle_id"] is None
        assert isinstance(d["id"], int) and d["id"] >= 1
        # start_time / end_time are returned as ISO strings; compare roughly
        assert isinstance(d["start_time"], str)
        assert isinstance(d["end_time"], str)

    def test_book_twice_returns_404(self, client, auth_headers, share_listing):
        """First booking sets listing status to 'booked'; second attempt returns 404."""
        start = _future(2)
        end = start + timedelta(hours=3)
        resp = client.post("/api/v1/residential/shares/book", json={
            "share_listing_id": share_listing["id"],
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text

        resp = client.post("/api/v1/residential/shares/book", json={
            "share_listing_id": share_listing["id"],
            "start_time": _future(6).isoformat(),
            "end_time": _future(9).isoformat(),
        }, headers=auth_headers)
        assert resp.status_code == 404, resp.text
        assert resp.json()["detail"] == "Share listing not found or not available"

    def test_book_outside_availability(self, client, auth_headers, seeded_lot):
        resp = client.post("/api/v1/residential/permits", json={
            "lot_id": seeded_lot, "slot_index": 6, "permit_type": "monthly",
            "start_date": "2025-01-01", "end_date": "2025-12-31",
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        pid = resp.json()["id"]

        resp = client.post("/api/v1/residential/shares", json={
            "resident_profile_id": pid, "price_per_hour": 5.0,
            "available_from": "08:00", "available_until": "10:00",
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        listing_id = resp.json()["id"]

        start = _future(2).replace(hour=20, minute=0)
        end = start + timedelta(hours=1)
        resp = client.post("/api/v1/residential/shares/book", json={
            "share_listing_id": listing_id,
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        }, headers=auth_headers)
        assert resp.status_code == 400, resp.text
        assert "Booking must be within" in resp.json()["detail"]

    def test_book_past_start(self, client, auth_headers, share_listing):
        past = _future(-1)
        end = past + timedelta(hours=1)
        resp = client.post("/api/v1/residential/shares/book", json={
            "share_listing_id": share_listing["id"],
            "start_time": past.isoformat(),
            "end_time": end.isoformat(),
        }, headers=auth_headers)
        assert resp.status_code == 400, resp.text
        assert resp.json()["detail"] == "start_time must be in the future"

    def test_book_listing_not_found(self, client, auth_headers):
        start = _future(2)
        end = start + timedelta(hours=1)
        resp = client.post("/api/v1/residential/shares/book", json={
            "share_listing_id": 99999,
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        }, headers=auth_headers)
        assert resp.status_code == 404, resp.text
        assert resp.json()["detail"] == "Share listing not found or not available"

    # ── GET /shares/bookings ────────────────────────────────────────────────

    def test_list_share_bookings(self, client, auth_headers, share_listing):
        start = _future(2)
        end = start + timedelta(hours=1)
        resp = client.post("/api/v1/residential/shares/book", json={
            "share_listing_id": share_listing["id"],
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text

        resp = client.get("/api/v1/residential/shares/bookings", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert isinstance(data, list)
        assert any(b["driver_name"] == "Test User" for b in data)

    def test_list_share_bookings_empty(self, client, alt_auth_headers):
        resp = client.get("/api/v1/residential/shares/bookings", headers=alt_auth_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json() == []

    # ── POST /shares/booking/{id}/cancel ─────────────────────────────────────

    def test_cancel_booking(self, client, auth_headers, share_listing):
        start = _future(2)
        end = start + timedelta(hours=1)
        resp = client.post("/api/v1/residential/shares/book", json={
            "share_listing_id": share_listing["id"],
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        bid = resp.json()["id"]

        resp = client.post(f"/api/v1/residential/shares/booking/{bid}/cancel", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "cancelled"
        assert resp.json()["booking_id"] == bid

    def test_cancel_booking_twice(self, client, auth_headers, share_listing):
        start = _future(2)
        end = start + timedelta(hours=1)
        resp = client.post("/api/v1/residential/shares/book", json={
            "share_listing_id": share_listing["id"],
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        bid = resp.json()["id"]

        client.post(f"/api/v1/residential/shares/booking/{bid}/cancel", headers=auth_headers)
        resp = client.post(f"/api/v1/residential/shares/booking/{bid}/cancel", headers=auth_headers)
        assert resp.status_code == 400, resp.text
        assert resp.json()["detail"] == "Only active bookings can be cancelled"

    def test_cancel_booking_not_found(self, client, auth_headers):
        resp = client.post("/api/v1/residential/shares/booking/99999/cancel", headers=auth_headers)
        assert resp.status_code == 404, resp.text
        assert resp.json()["detail"] == "Booking not found"

    # ── DELETE /shares/{listing_id} ──────────────────────────────────────────

    def test_cancel_share_listing(self, client, auth_headers, share_listing):
        resp = client.delete(
            f"/api/v1/residential/shares/{share_listing['id']}", headers=auth_headers
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "cancelled"
        assert resp.json()["listing_id"] == share_listing["id"]

    def test_cancel_listing_with_active_bookings(self, client, auth_headers, share_listing):
        start = _future(2)
        end = start + timedelta(hours=1)
        resp = client.post("/api/v1/residential/shares/book", json={
            "share_listing_id": share_listing["id"],
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text

        resp = client.delete(
            f"/api/v1/residential/shares/{share_listing['id']}", headers=auth_headers
        )
        assert resp.status_code == 409, resp.text
        assert resp.json()["detail"] == "Cannot cancel listing with active bookings"

    def test_cancel_listing_not_found(self, client, auth_headers):
        resp = client.delete("/api/v1/residential/shares/99999", headers=auth_headers)
        assert resp.status_code == 404, resp.text
        assert resp.json()["detail"] == "Listing not found"

    # ── PUT /permits/{id}/vehicle ────────────────────────────────────────────

    def test_register_vehicle(self, client, auth_headers, resident_permit):
        resp = client.put(
            f"/api/v1/residential/permits/{resident_permit['id']}/vehicle",
            json={"vehicle_id": "MH12AB1234"}, headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["registered_vehicle"] == "MH12AB1234"

    def test_register_vehicle_invalid_pattern(self, client, auth_headers, resident_permit):
        resp = client.put(
            f"/api/v1/residential/permits/{resident_permit['id']}/vehicle",
            json={"vehicle_id": "invalid"}, headers=auth_headers,
        )
        assert resp.status_code == 422, resp.text

    def test_register_vehicle_permit_not_found(self, client, auth_headers):
        resp = client.put(
            "/api/v1/residential/permits/99999/vehicle",
            json={"vehicle_id": "MH12AB1234"}, headers=auth_headers,
        )
        assert resp.status_code == 404, resp.text
        assert resp.json()["detail"] == "Permit not found"

    # ── DELETE /permits/{id}/vehicle ─────────────────────────────────────────

    def test_unregister_vehicle(self, client, auth_headers, resident_permit):
        client.put(
            f"/api/v1/residential/permits/{resident_permit['id']}/vehicle",
            json={"vehicle_id": "MH12AB1234"}, headers=auth_headers,
        )
        resp = client.delete(
            f"/api/v1/residential/permits/{resident_permit['id']}/vehicle",
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["registered_vehicle"] is None

    # ── POST /permits/{id}/deactivate ────────────────────────────────────────

    def test_deactivate_permit(self, client, auth_headers, resident_permit):
        resp = client.post(
            f"/api/v1/residential/permits/{resident_permit['id']}/deactivate",
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["is_active"] is False

    def test_deactivate_permit_with_active_shares(self, client, auth_headers, share_listing, resident_permit):
        resp = client.post(
            f"/api/v1/residential/permits/{resident_permit['id']}/deactivate",
            headers=auth_headers,
        )
        assert resp.status_code == 409, resp.text
        assert resp.json()["detail"] == (
            "Cannot deactivate permit with active share listings. Cancel them first."
        )

    def test_deactivate_permit_not_found(self, client, auth_headers):
        resp = client.post(
            "/api/v1/residential/permits/99999/deactivate", headers=auth_headers
        )
        assert resp.status_code == 404, resp.text
        assert resp.json()["detail"] == "Permit not found"

    def test_deactivate_permit_already_deactivated(self, client, auth_headers, seeded_lot):
        resp = client.post("/api/v1/residential/permits", json={
            "lot_id": seeded_lot, "slot_index": 7, "permit_type": "monthly",
            "start_date": "2025-01-01", "end_date": "2025-12-31",
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        pid = resp.json()["id"]

        client.post(f"/api/v1/residential/permits/{pid}/deactivate", headers=auth_headers)
        resp = client.post(
            f"/api/v1/residential/permits/{pid}/deactivate", headers=auth_headers
        )
        assert resp.status_code == 400, resp.text
        assert resp.json()["detail"] == "Permit is already deactivated"

    # ── Auth Enforcement ─────────────────────────────────────────────────────

    def test_all_post_put_delete_return_401_without_auth(self, client):
        routes = [
            ("POST", "/api/v1/residential/permits", {"lot_id": "x", "slot_index": 1, "permit_type": "monthly", "start_date": "2025-01-01", "end_date": "2025-12-31"}),
            ("POST", "/api/v1/residential/shares", {"resident_profile_id": 1, "price_per_hour": 5.0}),
            ("POST", "/api/v1/residential/shares/book", {"share_listing_id": 1, "start_time": "2025-01-01T00:00:00", "end_time": "2025-01-01T01:00:00"}),
            ("PUT", "/api/v1/residential/permits/1/vehicle", {"vehicle_id": "MH12AB1234"}),
            ("DELETE", "/api/v1/residential/shares/1", None),
            ("DELETE", "/api/v1/residential/permits/1/vehicle", None),
            ("POST", "/api/v1/residential/shares/booking/1/cancel", None),
            ("POST", "/api/v1/residential/permits/1/deactivate", None),
        ]
        for method, url, body in routes:
            kwargs = {"headers": {}}
            if body is not None:
                kwargs["json"] = body
            resp = getattr(client, method.lower())(url, **kwargs)
            assert resp.status_code == 401, f"{method} {url} returned {resp.status_code}, expected 401"


# ═══════════════════════════════════════════════════════════════════════════
# Sub-Plan 06: Phase 10 — Full End-to-End Lifecycle
# ═══════════════════════════════════════════════════════════════════════════

class TestResidentialE2E:
    """Single comprehensive walk through the resident share parking lifecycle
    with TWO parallel drivers. Every intermediate state asserted exactly."""

    def test_full_residential_lifecycle_e2e(self, client, auth_headers, admin_headers):
        # We drive Driver B through Bearer tokens only; clear any auth cookies
        # (get_current_user reads the cookie FIRST and would override Bearer).
        b_token = _ensure_user(client, "alt_e2e@pragma.io", "Driver123!", "Alt Driver")
        client.cookies.clear()
        alt_headers = {"Authorization": f"Bearer {b_token}"}

        # ── Step 1: Admin creates lot and seeds slots ───────────────────────
        resp = client.post("/api/v1/lots", json={
            "lot_id": "e2e_lot", "name": "E2E Test Lot",
            "total_slots": 10, "base_price": 10.0, "price_cap": 50.0,
        }, headers=admin_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["lot_id"] == "e2e_lot"
        assert resp.json()["status"] == "created"

        resp = client.post(
            "/api/v1/micro/lots/e2e_lot/slots/seed", headers=admin_headers
        )
        assert resp.status_code == 200, resp.text
        # total_slots == 10 is reflected in the seeded slot population.
        resp = client.get(
            "/api/v1/micro/lots/e2e_lot/slots", headers=admin_headers
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["total_slots"] == 10

        # ── Step 2: Driver A creates resident permit (slot_index 1) ──────────
        resp = client.post("/api/v1/residential/permits", json={
            "lot_id": "e2e_lot", "slot_index": 1, "permit_type": "monthly",
            "start_date": "2025-01-01", "end_date": "2025-12-31",
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        permit = resp.json()
        permit_id = permit["id"]
        assert permit_id >= 1
        assert permit["lot_id"] == "e2e_lot"
        assert permit["slot_index"] == 1
        assert permit["permit_type"] == "monthly"
        assert permit["is_active"] is True
        assert permit["monthly_rate"] == 50.0
        assert permit["registered_vehicle"] is None
        assert permit["user_email"] == "test@pragma.io"

        # ── Step 3: Driver A registers vehicle ──────────────────────────────
        resp = client.put(
            f"/api/v1/residential/permits/{permit_id}/vehicle",
            json={"vehicle_id": "MH12AB1234"}, headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["registered_vehicle"] == "MH12AB1234"

        # ── Step 4: Driver A creates share listing ──────────────────────────
        resp = client.post("/api/v1/residential/shares", json={
            "resident_profile_id": permit_id,
            "price_per_hour": 5.0,
            "available_from": "06:00",
            "available_until": "22:00",
            "max_advance_days": 14,
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        listing = resp.json()
        listing_id = listing["id"]
        assert listing["status"] == SHARE_LISTING_ACTIVE
        assert listing["price_per_hour"] == 5.0
        assert listing["available_from"] == "06:00"
        assert listing["available_until"] == "22:00"
        assert listing["max_advance_days"] == 14
        assert listing["slot_index"] == 1
        assert listing["resident_name"] == "Test User"
        assert listing["registered_vehicle"] == "MH12AB1234"

        # ── Step 5: Driver A lists their permits ────────────────────────────
        resp = client.get("/api/v1/residential/permits", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        permits = resp.json()
        assert any(
            p["id"] == permit_id and p["is_active"] is True for p in permits
        )

        # ── Step 6: Admin lists permit slots for the lot ────────────────────
        resp = client.get(
            "/api/v1/residential/permits/e2e_lot/slots", headers=admin_headers
        )
        assert resp.status_code == 200, resp.text
        slots = resp.json()
        assert any(
            s["slot_index"] == 1 and s["permit_type"] == "monthly" and s["is_active"] is True
            for s in slots
        )

        # ── Step 7: Driver B browses available shares ───────────────────────
        resp = client.get("/api/v1/residential/shares", headers=alt_headers)
        assert resp.status_code == 200, resp.text
        shares = resp.json()
        assert any(
            s["id"] == listing_id and s["price_per_hour"] == 5.0
            and s["slot_index"] == 1 and s["status"] == SHARE_LISTING_ACTIVE
            for s in shares
        )

        # ── Step 8: Driver B books the share (future window) ────────────────
        start = _future(3)
        end = start + timedelta(hours=2)
        resp = client.post("/api/v1/residential/shares/book", json={
            "share_listing_id": listing_id,
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        }, headers=alt_headers)
        assert resp.status_code == 201, resp.text
        booking = resp.json()
        booking_id = booking["id"]
        assert booking["status"] == SHARE_BOOKING_ACTIVE
        assert booking["share_listing_id"] == listing_id
        assert booking["total_cost"] == round(2 * 5.0, 2) == 10.0
        assert booking["platform_fee"] == round(10.0 * 0.10, 2) == 1.0
        assert booking["owner_payout"] == round(10.0 - 1.0, 2) == 9.0
        assert booking["driver_name"] == "Alt Driver"
        assert booking["slot_index"] == 1
        assert booking["start_time"] is not None
        assert booking["end_time"] is not None

        # ── Step 9: Booked listing no longer appears in browse ──────────────
        resp = client.get("/api/v1/residential/shares", headers=alt_headers)
        assert resp.status_code == 200, resp.text
        browse_ids = [s["id"] for s in resp.json()]
        assert listing_id not in browse_ids

        # ── Step 10: Re-book same listing → 404 (now "booked", not available) ─
        # NOTE: booking uses status==SHARE_LISTING_ACTIVE lookup, so a booked
        # listing returns 404 ("not found or not available") before the 409
        # overlap check can fire. This is the real, reachable behavior.
        resp = client.post("/api/v1/residential/shares/book", json={
            "share_listing_id": listing_id,
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        }, headers=alt_headers)
        assert resp.status_code == 404, resp.text

        # ── Step 11: Driver B lists their bookings ──────────────────────────
        resp = client.get(
            "/api/v1/residential/shares/bookings", headers=alt_headers
        )
        assert resp.status_code == 200, resp.text
        assert any(b["id"] == booking_id and b["status"] == SHARE_BOOKING_ACTIVE
                   for b in resp.json())

        # ── Step 12: Driver B cancels the booking ───────────────────────────
        resp = client.post(
            f"/api/v1/residential/shares/booking/{booking_id}/cancel",
            headers=alt_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"status": "cancelled", "booking_id": booking_id}

        # ── Step 13: Listing reverts to active and reappears in browse ──────
        resp = client.get("/api/v1/residential/shares", headers=alt_headers)
        assert resp.status_code == 200, resp.text
        assert any(
            s["id"] == listing_id and s["status"] == SHARE_LISTING_ACTIVE
            for s in resp.json()
        )

        # ── Step 14: Cancel the share listing (a deactivated permit requires
        #            no active listings), then unregister the vehicle (which
        #            requires an ACTIVE permit), then deactivate the permit. ──
        resp = client.delete(
            f"/api/v1/residential/shares/{listing_id}", headers=auth_headers
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "cancelled"

        resp = client.delete(
            f"/api/v1/residential/permits/{permit_id}/vehicle", headers=auth_headers
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["registered_vehicle"] is None

        resp = client.post(
            f"/api/v1/residential/permits/{permit_id}/deactivate",
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        dep = resp.json()
        assert dep["is_active"] is False
        assert dep["registered_vehicle"] is None

        # ── Step 15: Final permit list reflects deactivation ─────────────────
        resp = client.get("/api/v1/residential/permits", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        assert any(
            p["id"] == permit_id and p["is_active"] is False
            and p["registered_vehicle"] is None
            for p in resp.json()
        )

    def test_settle_flow_with_blockchain(self, client, auth_headers, admin_headers):
        # Distinct lot/slot so it never collides with the lifecycle test.
        resp = client.post("/api/v1/lots", json={
            "lot_id": "settle_lot", "name": "Settle Lot",
            "total_slots": 10, "base_price": 10.0, "price_cap": 50.0,
        }, headers=admin_headers)
        assert resp.status_code == 200, resp.text
        resp = client.post(
            "/api/v1/micro/lots/settle_lot/slots/seed", headers=admin_headers
        )
        assert resp.status_code == 200, resp.text

        resp = client.post("/api/v1/residential/permits", json={
            "lot_id": "settle_lot", "slot_index": 2, "permit_type": "monthly",
            "start_date": "2025-01-01", "end_date": "2025-12-31",
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        permit_id = resp.json()["id"]

        resp = client.put(
            f"/api/v1/residential/permits/{permit_id}/vehicle",
            json={"vehicle_id": "MH12AB1234"}, headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text

        resp = client.post("/api/v1/residential/shares", json={
            "resident_profile_id": permit_id,
            "price_per_hour": 5.0,
            "available_from": "06:00",
            "available_until": "22:00",
            "max_advance_days": 14,
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        listing_id = resp.json()["id"]

        # Book a future window, then rewrite its times into the past via DB.
        start = _future(3)
        end = start + timedelta(hours=2)
        resp = client.post("/api/v1/residential/shares/book", json={
            "share_listing_id": listing_id,
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        booking_id = resp.json()["id"]

        db = get_session()
        booking = db.query(ShareBooking).filter(ShareBooking.id == booking_id).first()
        booking.start_time = datetime(2020, 1, 1, 8, 0, 0)
        booking.end_time = datetime(2020, 1, 1, 10, 0, 0)
        db.commit()
        db.close()

        resp = client.post(
            f"/api/v1/residential/shares/booking/{booking_id}/settle",
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        settled = resp.json()
        assert settled["status"] == "completed"
        assert settled["booking_id"] == booking_id
        assert settled["platform_fee"] == 1.0
        assert settled["owner_payout"] == 9.0
        assert settled["blockchain_ref"] is None or isinstance(
            settled["blockchain_ref"], str
        )

        # Verify DB state.
        db = get_session()
        booking = db.query(ShareBooking).filter(ShareBooking.id == booking_id).first()
        assert booking.status == SHARE_BOOKING_COMPLETED
        listing = db.query(ShareListing).filter(ShareListing.id == listing_id).first()
        assert listing.status == SHARE_LISTING_ACTIVE
        db.close()

        # Verify ledger contains a share_settlement entry for this booking.
        pipeline.ledger.mine_pending()
        entries = [
            tx for block in pipeline.ledger.chain
            for tx in block.transactions
            if tx.get("action") == TX_ACTION_SHARE_SETTLEMENT
        ]
        assert any(tx.get("booking_id") == booking_id for tx in entries)


class TestResidentialErrors:
    """Error-boundary tests for residential endpoints."""

    def test_403_driver_cannot_cancel_others_booking(
        self, client, auth_headers, admin_headers
    ):
        # Admin seeds a lot + a Driver A permit/listing/booking, then Driver B
        # attempts to cancel the booking → 403 authorization error.
        resp = client.post("/api/v1/lots", json={
            "lot_id": "err_lot", "name": "Err Lot",
            "total_slots": 10, "base_price": 10.0, "price_cap": 50.0,
        }, headers=admin_headers)
        assert resp.status_code == 200, resp.text
        resp = client.post(
            "/api/v1/micro/lots/err_lot/slots/seed", headers=admin_headers
        )
        assert resp.status_code == 200, resp.text

        resp = client.post("/api/v1/residential/permits", json={
            "lot_id": "err_lot", "slot_index": 1, "permit_type": "monthly",
            "start_date": "2025-01-01", "end_date": "2025-12-31",
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        permit_id = resp.json()["id"]
        resp = client.put(
            f"/api/v1/residential/permits/{permit_id}/vehicle",
            json={"vehicle_id": "MH12AB1234"}, headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        resp = client.post("/api/v1/residential/shares", json={
            "resident_profile_id": permit_id, "price_per_hour": 5.0,
            "available_from": "06:00", "available_until": "22:00",
            "max_advance_days": 14,
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        listing_id = resp.json()["id"]
        start = _future(3)
        end = start + timedelta(hours=2)
        resp = client.post("/api/v1/residential/shares/book", json={
            "share_listing_id": listing_id,
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        booking_id = resp.json()["id"]

        b_token = _ensure_user(client, "err_intruder@pragma.io", "Driver123!", "Intruder")
        client.cookies.clear()
        intruder_headers = {"Authorization": f"Bearer {b_token}"}

        resp = client.post(
            f"/api/v1/residential/shares/booking/{booking_id}/cancel",
            headers=intruder_headers,
        )
        assert resp.status_code == 403, resp.text

    def test_404_nonexistent_settle(self, client, auth_headers):
        resp = client.post(
            "/api/v1/residential/shares/booking/99999/settle", headers=auth_headers
        )
        assert resp.status_code == 404, resp.text
        assert resp.json()["detail"] == "Booking not found"

    def test_admin_ops_return_403_for_driver(self, client, auth_headers, admin_headers):
        # Driver A (auth_headers) must NOT be able to act on resources
        # owned by a different driver B (the _ensure_user owner).
        resp = client.post("/api/v1/lots", json={
            "lot_id": "admin403_lot", "name": "Admin403 Lot",
            "total_slots": 10, "base_price": 10.0, "price_cap": 50.0,
        }, headers=admin_headers)
        assert resp.status_code == 200, resp.text
        resp = client.post(
            "/api/v1/micro/lots/admin403_lot/slots/seed", headers=admin_headers
        )
        assert resp.status_code == 200, resp.text

        owner_token = _ensure_user(
            client, "owner403@pragma.io", "Owner403!", "Owner FourOThree"
        )
        # Login set a pragma_token cookie; clear it so the Bearer header
        # (Driver A, below) takes priority over the cookie (owner B).
        client.cookies.clear()
        owner_headers = {"Authorization": f"Bearer {owner_token}"}

        resp = client.post("/api/v1/residential/permits", json={
            "lot_id": "admin403_lot", "slot_index": 1, "permit_type": "monthly",
            "start_date": "2025-01-01", "end_date": "2025-12-31",
        }, headers=owner_headers)
        assert resp.status_code == 201, resp.text
        permit_id = resp.json()["id"]

        resp = client.post("/api/v1/residential/shares", json={
            "resident_profile_id": permit_id, "price_per_hour": 5.0,
        }, headers=owner_headers)
        assert resp.status_code == 201, resp.text
        listing_id = resp.json()["id"]

        start = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        end = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()
        resp = client.post("/api/v1/residential/shares/book", json={
            "share_listing_id": listing_id, "start_time": start, "end_time": end,
        }, headers=owner_headers)
        assert resp.status_code == 201, resp.text
        booking_id = resp.json()["id"]

        # Driver A attempts owner/admin-only ops on B's resources.
        resp = client.post(
            f"/api/v1/residential/permits/{permit_id}/deactivate",
            headers=auth_headers,
        )
        assert resp.status_code == 403, resp.text
        assert "Not authorized" in resp.json()["detail"]

        resp = client.post(
            f"/api/v1/residential/shares/booking/{booking_id}/settle",
            json={"payout_to_resident": True}, headers=auth_headers,
        )
        assert resp.status_code == 403, resp.text
        assert "Not authorized" in resp.json()["detail"]
