import pytest
from datetime import datetime, timezone, timedelta
from src.api.database import (
    get_session,
    User,
    PrebookRecord,
    ParkingSession,
    Transaction,
)


def _create_lot(lot_id="prebook_fin_lot"):
    db = get_session()
    try:
        from src.api.database import ParkingLot

        if (
            not db.query(ParkingLot)
            .filter(ParkingLot.lot_id == lot_id)
            .first()
        ):
            db.add(
                ParkingLot(
                    lot_id=lot_id,
                    name="Finance Test Lot",
                    total_slots=10,
                    base_price=10.0,
                    price_cap=50.0,
                )
            )
            db.commit()
    finally:
        db.close()


class TestPrebookFinanceFlow:
    @pytest.fixture
    def setup_driver(self, client):
        # 1. Register a driver and seed driver wallet with $100.
        email = "fin_driver@pragma.io"
        password = "FinPass123!"
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "full_name": "Finance Driver",
            },
        )
        assert resp.status_code == 200
        token = resp.json().get("access_token", "")
        headers = {"Authorization": f"Bearer {token}"}

        # Top up wallet to 100.0
        topup_resp = client.post(
            "/api/v1/wallet/topup", json={"amount": 100.0}, headers=headers
        )
        assert topup_resp.status_code == 200

        # Verify initial balance is 100.0
        db = get_session()
        try:
            user = db.query(User).filter(User.email == email).first()
            assert user is not None
            assert user.balance == 100.0
        finally:
            db.close()
        return email, headers

    def test_prebook_finance_integration_flow(
        self, client, setup_driver, admin_headers
    ):
        email, headers = setup_driver
        lot_id = "prebook_fin_lot"
        _create_lot(lot_id)

        # Seed micro slots. Clear cookies so admin_headers takes priority.
        client.cookies.clear()
        seed_resp = client.post(
            f"/api/v1/micro/lots/{lot_id}/slots/seed", headers=admin_headers
        )
        assert seed_resp.status_code == 200, seed_resp.text

        # Clear cookies again so headers (driver bearer token) takes priority
        client.cookies.clear()

        # 2. Create a prebooking for a slot (booking fee $2 + deposit $10).
        target_time = (
            datetime.now(timezone.utc) + timedelta(hours=1)
        ).isoformat()
        prebook_resp = client.post(
            "/api/v1/micro/prebook",
            json={
                "lot_id": lot_id,
                "slots": [{"slot_index": 1, "priority": 1}],
                "target_time": target_time,
            },
            headers=headers,
        )
        assert prebook_resp.status_code == 200, prebook_resp.text
        prebook_data = prebook_resp.json()
        prebook_id = prebook_data["prebook_id"]

        # Assert driver balance is $88 (100 - 2 booking fee - 10 deposit).
        db = get_session()
        try:
            user = db.query(User).filter(User.email == email).first()
            assert user is not None
            assert float(user.balance) == 88.0

            # Check prebook record exists and is active
            pb_rec = (
                db.query(PrebookRecord)
                .filter(PrebookRecord.prebook_id == prebook_id)
                .first()
            )
            assert pb_rec is not None
            assert pb_rec.status == "active"
            assert float(pb_rec.booking_fee) == 2.0
            assert float(pb_rec.deposit) == 10.0

            # Check transaction records
            fee_tx = (
                db.query(Transaction)
                .filter(Transaction.tx_hash == f"fee_{prebook_id}")
                .first()
            )
            assert fee_tx is not None
            assert fee_tx.amount == 2.0
            assert fee_tx.action == "booking_fee"

            dep_tx = (
                db.query(Transaction)
                .filter(Transaction.tx_hash == f"deposit_{prebook_id}")
                .first()
            )
            assert dep_tx is not None
            assert dep_tx.amount == 10.0
            assert dep_tx.action == "deposit"
        finally:
            db.close()

        # 3. Confirm the prebooking to start a session.
        client.cookies.clear()
        confirm_resp = client.post(
            "/api/v1/micro/confirm",
            json={
                "prebook_id": prebook_id,
            },
            headers=headers,
        )
        assert confirm_resp.status_code == 200, confirm_resp.text
        confirm_data = confirm_resp.json()
        session_id = confirm_data["session_id"]

        db = get_session()
        try:
            # Check prebooking is now confirmed
            pb_rec = (
                db.query(PrebookRecord)
                .filter(PrebookRecord.prebook_id == prebook_id)
                .first()
            )
            assert pb_rec is not None
            assert pb_rec.status == "confirmed"

            # Check session is running
            sess = (
                db.query(ParkingSession)
                .filter(ParkingSession.session_id == session_id)
                .first()
            )
            assert sess is not None
            assert sess.status == "running"

            # Calculate hours to subtract to get exactly $6.0 charge
            entry_price = float(sess.entry_price)
            hours_to_subtract = 6.0 / entry_price

            # 4. Modify session start_time without buffer
            #    (delay increases time slightly, rounding up to $6.0)
            sess.start_time = datetime.now(timezone.utc) - timedelta(
                hours=hours_to_subtract
            )
            db.commit()
        finally:
            db.close()

        # End the session.
        client.cookies.clear()
        end_resp = client.post(
            "/api/v1/sessions/end",
            json={
                "session_id": session_id,
            },
            headers=headers,
        )
        assert end_resp.status_code == 200, end_resp.text
        end_data = end_resp.json()

        # Assert duration is as calculated, charge is $6.0, refund is $4.0.
        assert end_data["amount_charged"] == 6.0
        assert end_data["deposit_refund"] == 4.0

        # Assert driver balance is $92 (88.0 + 4.0 refund).
        db = get_session()
        try:
            user = db.query(User).filter(User.email == email).first()
            assert user is not None
            assert float(user.balance) == 92.0

            # Verify the correct refund Transaction log in the DB
            refund_tx = (
                db.query(Transaction)
                .filter(
                    Transaction.lot_id == lot_id,
                    Transaction.driver_id == email,
                    Transaction.action == "refund",
                    Transaction.amount == 4.0,
                )
                .first()
            )
            assert refund_tx is not None
            assert refund_tx.tx_hash == f"settle_{session_id}"

            # Prebook deposit should be marked refunded
            pb_rec = (
                db.query(PrebookRecord)
                .filter(PrebookRecord.prebook_id == prebook_id)
                .first()
            )
            assert pb_rec is not None
            assert pb_rec.deposit_refunded == 1
        finally:
            db.close()
