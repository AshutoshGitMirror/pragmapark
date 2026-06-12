import pytest
from src.api.database import (
    get_db_cm,
    OccupancyRecord,
    ParkingLot,
    Base,
    get_engine,
)
from src.api.utils import (
    get_latest_occupancies,
    get_recent_records,
    lot_to_summary,
)


@pytest.fixture(autouse=True)
def _setup_db():
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    yield
    engine.dispose()


class TestGetLatestOccupancies:
    def test_returns_empty_for_empty_list(self):
        with get_db_cm() as db:
            assert get_latest_occupancies(db, []) == {}

    def test_returns_latest_record_per_lot(self):
        with get_db_cm() as db:
            lot = ParkingLot(lot_id="test_lot", name="Test", total_slots=100)
            db.add(lot)
            db.flush()
            db.add(
                OccupancyRecord(
                    lot_id="test_lot",
                    occupied_slots=30,
                    total_slots=100,
                    occupancy_rate=0.3,
                    price=10.0,
                )
            )
            db.add(
                OccupancyRecord(
                    lot_id="test_lot",
                    occupied_slots=50,
                    total_slots=100,
                    occupancy_rate=0.5,
                    price=15.0,
                )
            )
            db.commit()
            result = get_latest_occupancies(db, ["test_lot"])
            assert "test_lot" in result
            assert result["test_lot"].occupancy_rate == 0.5


class TestGetRecentRecords:
    def test_returns_empty_for_unknown_lot(self):
        with get_db_cm() as db:
            assert get_recent_records(db, "nonexistent") == []

    def test_returns_limited_records(self):
        with get_db_cm() as db:
            lot = ParkingLot(
                lot_id="test_recent", name="Test", total_slots=100
            )
            db.add(lot)
            db.flush()
            for i in range(15):
                db.add(
                    OccupancyRecord(
                        lot_id="test_recent",
                        occupied_slots=i,
                        total_slots=100,
                        occupancy_rate=i / 100,
                        price=10.0,
                    )
                )
            db.commit()
            result = get_recent_records(db, "test_recent", limit=5)
            assert len(result) == 5
            assert (
                result[0].occupied_slots > result[-1].occupied_slots
            )  # desc order


class TestLotToSummary:
    def test_basic_summary(self):
        with get_db_cm() as db:
            lot = ParkingLot(
                lot_id="lot1",
                name="Lot One",
                address="123 St",
                city="City",
                total_slots=200,
                latitude=1.0,
                longitude=2.0,
                base_price=10.0,
                price_cap=50.0,
            )
            db.add(lot)
            db.commit()
            summary = lot_to_summary(lot)
            assert summary["lot_id"] == "lot1"
            assert summary["name"] == "Lot One"
            assert summary["total_slots"] == 200
            assert summary["current_occupancy"] == 0

    def test_with_latest_record(self):
        with get_db_cm() as db:
            lot = ParkingLot(
                lot_id="lot2",
                name="Lot Two",
                total_slots=100,
                base_price=10.0,
                price_cap=50.0,
            )
            db.add(lot)
            db.flush()
            rec = OccupancyRecord(
                lot_id="lot2",
                occupied_slots=80,
                total_slots=100,
                occupancy_rate=0.8,
                price=12.0,
            )
            db.add(rec)
            db.commit()
            summary = lot_to_summary(lot, rec)
            assert summary["current_occupancy"] == 80.0
            assert summary["current_price"] == 12.0

    def test_nullable_fields_default_to_empty(self):
        lot = ParkingLot(
            lot_id="lot3",
            name="Lot Three",
            total_slots=50,
            base_price=5.0,
            price_cap=25.0,
        )
        summary = lot_to_summary(lot)
        assert summary["address"] == ""
        assert summary["latitude"] == 0.0


class TestGetDb:
    def test_get_db_yields_session_and_closes(self):
        with get_db_cm() as db:
            assert db is not None
            from sqlalchemy import text

            db.execute(text("SELECT 1"))
