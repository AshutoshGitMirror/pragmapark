import os
import json
import tempfile
from src.blockchain.ledger import BlockchainLedger, Block


class TestBlock:
    def test_compute_hash_returns_string(self):
        b = Block(index=0, timestamp=0.0, transactions=[], previous_hash="0" * 64)
        h = b.compute_hash()
        assert isinstance(h, str)
        assert len(h) == 64

    def test_mine_adds_nonce(self):
        b = Block(index=0, timestamp=0.0, transactions=[], previous_hash="0" * 64)
        old_nonce = b.nonce
        b.mine(difficulty=1)
        assert b.nonce >= old_nonce
        assert b.hash.startswith("0")

    def test_post_init_computes_hash(self):
        b = Block(index=0, timestamp=0.0, transactions=[], previous_hash="0" * 64)
        assert len(b.hash) == 64


class TestBlockchainLedger:
    def test_constructor_creates_genesis(self):
        ledger = BlockchainLedger(difficulty=1)
        assert len(ledger.chain) == 1
        assert ledger.chain[0].index == 0

    def test_add_transaction_returns_index(self):
        ledger = BlockchainLedger(difficulty=1)
        idx = ledger.add_transaction({"type": "test"})
        assert idx == 1

    def test_mine_pending_creates_block(self):
        ledger = BlockchainLedger(difficulty=1)
        ledger.add_transaction({"type": "test"})
        block = ledger.mine_pending()
        assert block.index == 1
        assert len(block.transactions) == 1
        assert len(ledger.pending_transactions) == 0

    def test_validate_chain_returns_true(self):
        ledger = BlockchainLedger(difficulty=1)
        ledger.add_transaction({"type": "test"})
        ledger.mine_pending()
        assert ledger.validate_chain() is True

    def test_validate_chain_returns_false_after_tamper(self):
        ledger = BlockchainLedger(difficulty=1)
        ledger.chain[0].transactions = [{"type": "tampered"}]
        assert ledger.validate_chain() is False

    def test_get_balance_initial(self):
        ledger = BlockchainLedger(difficulty=1)
        assert ledger.get_balance("driver_1") == 0.0

    def test_get_balance_after_payment(self):
        ledger = BlockchainLedger(difficulty=1)
        ledger.add_transaction({"driver_id": "d1", "action": "session_fee", "amount": 10.0})
        ledger.mine_pending()
        assert ledger.get_balance("d1") == -10.0

    def test_get_balance_after_refund(self):
        ledger = BlockchainLedger(difficulty=1)
        ledger.add_transaction({"driver_id": "d1", "action": "refund", "amount": 5.0})
        ledger.mine_pending()
        assert ledger.get_balance("d1") == 5.0

    def test_has_tx_hash_found(self):
        ledger = BlockchainLedger(difficulty=1)
        ledger.add_transaction({"tx_hash": "abc123"})
        ledger.mine_pending()
        assert ledger.has_tx_hash("abc123") is True

    def test_has_tx_hash_not_found(self):
        ledger = BlockchainLedger(difficulty=1)
        assert ledger.has_tx_hash("nonexistent") is False

    def test_has_tx_hash_empty(self):
        ledger = BlockchainLedger(difficulty=1)
        assert ledger.has_tx_hash("") is False

    def test_last_block_property(self):
        ledger = BlockchainLedger(difficulty=1)
        assert ledger.last_block.index == 0

    def test_save_and_load(self):
        ledger = BlockchainLedger(difficulty=1)
        ledger.add_transaction({"type": "test"})
        ledger.mine_pending()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            ledger.save_to_file(path)
            loaded = BlockchainLedger.load_from_file(path)
            assert loaded.validate_chain() is True
            assert len(loaded.chain) == 2
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_load_from_file_missing_returns_new(self):
        ledger = BlockchainLedger.load_from_file("/tmp/nonexistent_chain.json")
        assert ledger.validate_chain() is True

    def test_to_dict(self):
        ledger = BlockchainLedger(difficulty=1)
        d = ledger.to_dict()
        assert d["length"] == 1
        assert d["valid"] is True
        assert "last_block" in d
