import pytest
from datetime import datetime, timezone, timedelta

from src.constants import (
    SHARE_PLATFORM_FEE, TX_ACTION_SHARE_SETTLEMENT,
)
from src.api.database import get_session, ShareBooking, ShareListing
from src.pipeline.orchestrator import pipeline


class TestResidentialContract:

    def test_share_settlement_contract_lifecycle(self):
        contract = pipeline.share_settlement_contract
        initial_fees = contract.state.get("total_platform_fees", 0)
        initial_payouts = contract.state.get("total_owner_payouts", 0)
        initial_cancels = contract.state.get("total_cancellations", 0)

        result = contract.execute({"action": "create", "booking_id": 1})
        assert result["valid"] is True
        assert result["action"] == "create"
        assert result["booking_id"] == 1

        result = contract.execute({
            "action": "settle", "booking_id": 1,
            "platform_fee": 1.5, "owner_payout": 13.5,
        })
        assert result["valid"] is True
        assert result["action"] == "settle"
        assert result["booking_id"] == 1
        assert result["platform_fee"] == 1.5
        assert result["owner_payout"] == 13.5
        assert contract.state["total_platform_fees"] == initial_fees + 1.5
        assert contract.state["total_owner_payouts"] == initial_payouts + 13.5

        result = contract.execute({"action": "cancel", "booking_id": 2})
        assert result["valid"] is True
        assert result["action"] == "cancel"
        assert result["booking_id"] == 2
        assert contract.state["total_cancellations"] == initial_cancels + 1

    def test_share_settlement_contract_invalid_action(self):
        contract = pipeline.share_settlement_contract
        result = contract.execute({"action": "invalid_action", "booking_id": 1})
        assert result["valid"] is False
        assert result["reason"] == "Invalid action: invalid_action"

    def test_share_settlement_contract_missing_booking_id(self):
        contract = pipeline.share_settlement_contract
        result = contract.execute({"action": "create"})
        assert result["valid"] is False
        assert result["reason"] == "Missing booking_id"

    def test_payout_math_precision(self):
        total_cost = 15.0
        fee_rate = SHARE_PLATFORM_FEE
        platform_fee = round(total_cost * fee_rate, 2)
        owner_payout = round(total_cost - platform_fee, 2)
        assert platform_fee == 1.5
        assert owner_payout == 13.5
        assert platform_fee + owner_payout == total_cost

    def test_settle_share_booking(self, client, admin_headers, auth_headers):
        resp = client.post("/api/v1/lots", json={
            "lot_id": "settle_lot", "name": "Settle Lot",
            "total_slots": 10, "base_price": 10.0, "price_cap": 50.0,
        }, headers=admin_headers)
        assert resp.status_code == 200, resp.text

        resp = client.post("/api/v1/micro/lots/settle_lot/slots/seed", headers=admin_headers)
        assert resp.status_code == 200, resp.text

        resp = client.post("/api/v1/residential/permits", json={
            "lot_id": "settle_lot", "slot_index": 1, "permit_type": "monthly",
            "start_date": "2025-01-01", "end_date": "2025-12-31",
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        permit = resp.json()

        resp = client.post("/api/v1/residential/shares", json={
            "resident_profile_id": permit["id"], "price_per_hour": 5.0,
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        listing = resp.json()
        listing_id = listing["id"]

        start = datetime.now(timezone.utc) + timedelta(hours=2)
        end = start + timedelta(hours=3)
        resp = client.post("/api/v1/residential/shares/book", json={
            "share_listing_id": listing_id,
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        booking = resp.json()
        booking_id = booking["id"]
        assert booking["total_cost"] == 15.0
        assert booking["status"] == "active"

        db = get_session()
        try:
            b = db.query(ShareBooking).filter(ShareBooking.id == booking_id).first()
            assert b is not None
            b.start_time = datetime(2020, 1, 1, 9, 0, 0)
            b.end_time = datetime(2020, 1, 1, 12, 0, 0)
            db.commit()
        finally:
            db.close()

        resp = client.post(
            f"/api/v1/residential/shares/booking/{booking_id}/settle",
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "completed"
        assert data["booking_id"] == booking_id
        assert data["platform_fee"] == 1.5
        assert data["owner_payout"] == 13.5

        db = get_session()
        try:
            settled_booking = db.query(ShareBooking).filter(
                ShareBooking.id == booking_id
            ).first()
            assert settled_booking.status == "completed"
            settled_listing = db.query(ShareListing).filter(
                ShareListing.id == listing_id
            ).first()
            assert settled_listing.status == "active"
        finally:
            db.close()

        pipeline.ledger.mine_pending()
        txns = [
            tx for block in pipeline.ledger.chain
            for tx in block.transactions
            if tx.get("action") == TX_ACTION_SHARE_SETTLEMENT
            and tx.get("booking_id") == booking_id
        ]
        assert len(txns) >= 1
        txn = txns[0]
        assert txn["platform_fee"] == 1.5
        assert txn["owner_payout"] == 13.5
        assert txn["share_listing_id"] == listing_id
        assert txn["driver_id"] == "test@pragma.io"

        state = pipeline.share_settlement_contract.state
        assert state["total_platform_fees"] >= 1.5
        assert state["total_owner_payouts"] >= 13.5
