import uuid
from datetime import datetime, timezone
from src.api.schemas.sessions import SessionDetailResponse
from sqlalchemy import select
from src.api.database import (
    get_session,
    ParkingLot,
    MicroSlot,
    SlotCurrentState,
    User,
    ParkingSession,
)
from src.constants import SESSION_RUNNING
from src.micro.state_engine import SlotState


class TestMyActiveSession:
    def test_active_session_requires_auth(self, client):
        resp = client.get("/api/v1/sessions/active")
        assert resp.status_code in (401, 403)

    def test_active_session_returns_404_when_no_session(
        self, client, auth_headers
    ):
        resp = client.get("/api/v1/sessions/active", headers=auth_headers)
        assert resp.status_code == 404
        assert "No active session" in resp.text

    def _create_active_session_directly(
        self, client, email="test@pragma.io", lot_id="act_ses_lot"
    ):
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
                        name="Active Session Lot",
                        total_slots=10,
                        base_price=5.0,
                        price_cap=20.0,
                    )
                )
                db.commit()
            slots = (
                db.execute(select(MicroSlot).where(MicroSlot.lot_id == lot_id))
                .scalars()
                .all()
            )
            if not slots:
                slot = MicroSlot(
                    lot_id=lot_id,
                    slot_index=1,
                    row_label="A",
                    position=1,
                    slot_type="regular",
                    active=1,
                )
                db.add(slot)
                db.commit()
                db.refresh(slot)
                scs = SlotCurrentState(
                    slot_id=slot.id, state=SlotState.AVAILABLE, updated_at=0
                )
                db.add(scs)
                db.commit()
            else:
                slot = slots[0]
            user = (
                db.execute(select(User).where(User.email == email))
                .scalars()
                .first()
            )
            if user and user.balance == 0:
                user.balance = 100.0
                db.commit()
            session = ParkingSession(
                session_id=str(uuid.uuid4()),
                lot_id=lot_id,
                slot=1,
                driver_id=email,
                start_time=datetime.now(timezone.utc),
                status=SESSION_RUNNING,
                entry_price=5.0,
            )
            db.add(session)
            db.commit()
        finally:
            db.close()

    def test_active_session_returns_session_when_active(
        self, client, auth_headers
    ):
        self._create_active_session_directly(client)
        resp = client.get("/api/v1/sessions/active", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data is not None
        assert "slot" in data or "slot_index" in data
        assert "entry_price" in data or "price" in data
        assert "lot_id" in data

    def test_active_session_includes_slot_and_rate(self, client, auth_headers):
        self._create_active_session_directly(client)
        resp = client.get("/api/v1/sessions/active", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("entry_price", data.get("current_rate", 0)) > 0

    def test_active_session_matches_pydantic_schema(
        self, client, auth_headers
    ):
        self._create_active_session_directly(client)
        resp = client.get("/api/v1/sessions/active", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        if data:
            validated = SessionDetailResponse(**data)
            assert validated.lot_id is not None

    def test_active_session_returns_404_for_other_driver(
        self, client, auth_headers, admin_headers
    ):
        self._create_active_session_directly(client)
        # Admin has no active session
        resp = client.get("/api/v1/sessions/active", headers=admin_headers)
        assert resp.status_code == 404
