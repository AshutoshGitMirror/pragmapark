import time
from src.blockchain.transaction import ParkingTransaction, AllocationRecord
from src.constants import ALLOC_CONFIRMED


class TestParkingTransaction:
    def test_auto_hashes_on_init(self):
        tx = ParkingTransaction(driver_id="d1", lot_id="l1", spot_id="s1", action="session_fee", price=10.0, duration_minutes=60)
        assert tx.tx_hash is not None
        assert len(tx.tx_hash) == 64  # full 256-bit SHA-256 hex digest

    def test_different_inputs_different_hashes(self):
        tx1 = ParkingTransaction(driver_id="d1", lot_id="l1", spot_id="s1", action="session_fee", price=10.0, duration_minutes=60)
        tx2 = ParkingTransaction(driver_id="d2", lot_id="l1", spot_id="s1", action="session_fee", price=10.0, duration_minutes=60)
        assert tx1.tx_hash != tx2.tx_hash


class TestAllocationRecord:
    def test_elapsed_minutes_increases(self):
        now = time.time()
        rec = AllocationRecord(driver_id="d1", lot_id="l1", spot_id="s1", allocated_price=10.0, start_time=now, end_time=now + 3600)
        assert rec.elapsed_minutes() >= 0.0

    def test_to_dict(self):
        rec = AllocationRecord(driver_id="d1", lot_id="l1", spot_id="s1", allocated_price=10.0, start_time=100.0, end_time=3700.0, status=ALLOC_CONFIRMED, revenue_share=3.0)
        d = rec.to_dict()
        assert d["driver_id"] == "d1"
        assert d["allocated_price"] == 10.0
        assert d["status"] == ALLOC_CONFIRMED
        assert d["revenue_share"] == 3.0
