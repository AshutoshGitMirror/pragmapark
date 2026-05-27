import pytest
from src.api.database import get_session, ParkingLot, ParkingSession, PredictionMetric
from src.api.services.session_service import create_session


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    db = get_session()
    try:
        db.query(PredictionMetric).delete()
        db.query(ParkingSession).delete()
        db.query(ParkingLot).delete()
        db.commit()
    finally:
        db.close()


class TestCreateSession:
    def _create_lot(self, lot_id="svc_lot"):
        db = get_session()
        try:
            if not db.query(ParkingLot).filter(ParkingLot.lot_id == lot_id).first():
                db.add(ParkingLot(lot_id=lot_id, name="Svc Test", total_slots=100, base_price=10.0, price_cap=50.0))
                db.commit()
        finally:
            db.close()

    def test_requires_existing_lot(self):
        try:
            create_session("nonexistent", 1, "driver_1")
            assert False, "should raise RuntimeError"
        except RuntimeError as e:
            assert "lot not found" in str(e)

    def test_creates_session(self):
        self._create_lot()
        result = create_session("svc_lot", 1, "driver_1")
        assert result["session_id"] is not None
        assert "price_at_entry" in result
        assert result["driver_id"] == "driver_1"
        assert result["lot_id"] == "svc_lot"

    def test_creates_db_entry(self):
        self._create_lot()
        result = create_session("svc_lot", 1, "driver_1")
        db = get_session()
        try:
            sess = db.query(ParkingSession).filter(
                ParkingSession.session_id == result["session_id"]
            ).first()
            assert sess is not None
            assert sess.status == "active"
            assert sess.driver_id == "driver_1"
        finally:
            db.close()

    def test_creates_prediction_metric(self):
        self._create_lot()
        result = create_session("svc_lot", 1, "driver_1")
        db = get_session()
        try:
            metric = db.query(PredictionMetric).filter(
                PredictionMetric.session_id == result["session_id"]
            ).first()
            assert metric is not None
            assert metric.lot_id == "svc_lot"
        finally:
            db.close()

    def test_raises_on_duplicate_active(self):
        self._create_lot()
        create_session("svc_lot", 1, "driver_1")
        try:
            create_session("svc_lot", 2, "driver_1")
            assert False, "should raise"
        except RuntimeError as e:
            assert "active session" in str(e)

    def test_force_ends_previous(self):
        self._create_lot()
        create_session("svc_lot", 1, "driver_1")
        result = create_session("svc_lot", 2, "driver_1", force=True)
        assert result["session_id"] is not None
        db = get_session()
        try:
            old = db.query(ParkingSession).filter(
                ParkingSession.driver_id == "driver_1",
                ParkingSession.status == "active",
            ).all()
            assert len(old) == 1
        finally:
            db.close()
