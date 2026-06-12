import sys
import os

sys.path.append(os.getcwd())

from src.blockchain import (  # noqa: E402
    BlockchainLedger, ParkingPool, RevenueShareContract,
)


class TestBlockchain:
    def test_genesis_chain(self):
        ledger = BlockchainLedger(difficulty=1)
        assert len(ledger.chain) == 1
        assert ledger.chain[0].index == 0
        assert ledger.validate_chain()

    def test_add_and_mine_transaction(self):
        ledger = BlockchainLedger(difficulty=1)
        ledger.add_transaction(
            {"driver_id": "d1", "action": "session_fee", "price": 10}
        )
        ledger.mine_pending()
        assert len(ledger.chain) == 2
        assert len(ledger.chain[1].transactions) == 1

    def test_invalid_chain_detected(self):
        ledger = BlockchainLedger(difficulty=1)
        ledger.add_transaction(
            {"driver_id": "d1", "action": "session_fee", "price": 10}
        )
        ledger.mine_pending()
        ledger.chain[1].transactions[0]["price"] = 9999
        assert not ledger.validate_chain()

    def test_balance_tracking(self):
        ledger = BlockchainLedger(difficulty=1)
        ledger.add_transaction(
            {"driver_id": "d1", "action": "session_fee", "price": 15}
        )
        ledger.mine_pending()
        assert ledger.get_balance("d1") == -15.0

    def test_pool_allocation(self):
        pool = ParkingPool("test_pool", 10, "city")
        rec = pool.allocate("d1", "lot_1", 20.0, 60)
        assert rec is not None
        assert pool.available_spots() == 9
        assert pool.total_revenue() == 20.0

    def test_pool_release(self):
        pool = ParkingPool("test_pool", 5, "city")
        rec = pool.allocate("d1", "lot_1", 10.0, 30)
        assert rec is not None
        assert pool.release(rec.spot_id)
        assert not pool.release("nonexistent")

    def test_revenue_share_contract(self):
        contract = RevenueShareContract(
            "rs_1", "city", {"city": 0.7, "owner": 0.3}, system_fee_ratio=0.15
        )
        result = contract.execute({"price": 100})
        # 15% system fee deducted first: 15.0
        assert result["distributions"]["system"] == 15.0
        # Remaining 85.0 split 70/30: city=59.5, owner=25.5
        assert result["distributions"]["city"] == 59.5
        assert result["distributions"]["owner"] == 25.5
        assert abs(sum(result["distributions"].values()) - 100.0) < 0.01

    def test_revenue_share_zero_system_fee(self):
        contract = RevenueShareContract(
            "rs_2", "city", {"city": 0.7, "owner": 0.3}, system_fee_ratio=0.0
        )
        result = contract.execute({"price": 100})
        assert result["distributions"]["city"] == 70.0
        assert result["distributions"]["owner"] == 30.0
