import os
import time
import hashlib
import json
import fcntl
import logging
from typing import List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class Block:
    index: int
    timestamp: float
    transactions: List[dict]
    previous_hash: str
    nonce: int = 0
    hash: str = ""

    def __post_init__(self):
        if not self.hash:
            self.hash = self.compute_hash()

    def compute_hash(self) -> str:
        raw = f"{self.index}{self.timestamp}{json.dumps(self.transactions, sort_keys=True, default=str)}{self.previous_hash}{self.nonce}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def mine(self, difficulty: int = 2) -> None:
        target = "0" * difficulty
        while not self.hash.startswith(target):
            self.nonce += 1
            self.hash = self.compute_hash()
        
MAX_PENDING_TX = 10000
MAX_CHAIN_LENGTH = int(os.getenv("MAX_CHAIN_LENGTH", "100000"))
CHAIN_WARN_THRESHOLD = int(os.getenv("CHAIN_WARN_THRESHOLD", "10000"))

class BlockchainLedger:
    def __init__(self, difficulty: int = 2):
        self.difficulty = difficulty
        self.chain: List[Block] = []
        self.pending_transactions: List[dict] = []
        self._create_genesis()

    def _create_genesis(self, timestamp: Optional[float] = None) -> None:
        genesis = Block(
            index=0,
            timestamp=timestamp if timestamp is not None else time.time(),
            transactions=[{"type": "genesis", "data": "Smart Parking Genesis Block"}],
            previous_hash="0" * 64,
        )
        genesis.mine(self.difficulty)
        self.chain.append(genesis)

    def add_transaction(self, tx: dict) -> int:
        if len(self.pending_transactions) >= MAX_PENDING_TX:
            raise OverflowError(f"Pending transaction pool full ({MAX_PENDING_TX} max)")
        self.pending_transactions.append(tx)
        return self.last_block.index + 1

    def mine_pending(self) -> Block:
        if len(self.chain) > CHAIN_WARN_THRESHOLD:
            logger.warning("Chain length %d exceeds warning threshold %d; consider archiving old blocks (max %d)", len(self.chain), CHAIN_WARN_THRESHOLD, MAX_CHAIN_LENGTH)
        block = Block(
            index=self.last_block.index + 1,
            timestamp=time.time(),
            transactions=self.pending_transactions[:],
            previous_hash=self.last_block.hash,
        )
        block.mine(self.difficulty)
        self.chain.append(block)
        self.pending_transactions = []
        return block

    def validate_chain(self) -> bool:
        if not self.chain:
            return False
        genesis = self.chain[0]
        if genesis.hash != genesis.compute_hash():
            return False
        if genesis.previous_hash != "0" * 64:
            return False
        if not genesis.hash.startswith("0" * self.difficulty):
            return False
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]
            if current.hash != current.compute_hash():
                return False
            if current.previous_hash != previous.hash:
                return False
            if not current.hash.startswith("0" * self.difficulty):
                return False
        return True

    def get_balance(self, driver_id: str) -> float:
        balance = 0.0
        for block in self.chain:
            for tx in block.transactions:
                if tx.get("driver_id") == driver_id:
                    if tx.get("action") in ("session_fee", "payment", "park"):
                        balance -= tx.get("amount", tx.get("price", 0))
                    elif tx.get("action") == "refund":
                        balance += tx.get("amount", tx.get("price", 0))
        return balance

    def has_tx_hash(self, tx_hash: str) -> bool:
        if not tx_hash:
            return False
        for block in self.chain:
            for tx in block.transactions:
                if tx.get("tx_hash") == tx_hash:
                    return True
        for tx in self.pending_transactions:
            if tx.get("tx_hash") == tx_hash:
                return True
        return False

    @property
    def last_block(self) -> Block:
        return self.chain[-1]

    def save_to_file(self, path: str = "data/blockchain.json") -> None:
        logger.info("event=blockchain.save.written path=%s blocks=%d pending=%d", path, len(self.chain), len(self.pending_transactions))
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        data = {
            "difficulty": self.difficulty,
            "chain": [asdict(b) for b in self.chain],
            "pending": self.pending_transactions[:],
        }
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                json.dump(data, f, indent=2, default=str)
                f.flush()
                os.fsync(f.fileno())
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        os.replace(tmp, path)

    @classmethod
    def load_from_file(cls, path: str = "data/blockchain.json") -> "BlockchainLedger":
        logger.info("event=blockchain.load.received path=%s", path)
        try:
            with open(path) as f:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                    data = json.load(f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            ledger = cls(difficulty=data.get("difficulty", 2))
            ledger.chain = [Block(**b) for b in data["chain"]]
            ledger.pending_transactions = data.get("pending", [])
            if not ledger.validate_chain():
                logger.warning("event=blockchain.load.integrity_failed path=%s", path)
                cls._backup_corrupt_file(path)
                return cls()
            logger.info("event=blockchain.load.completed blocks=%d pending=%d", len(ledger.chain), len(ledger.pending_transactions))
            return ledger
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            logger.warning("event=blockchain.load.failed path=%s", path)
            cls._backup_corrupt_file(path)
            return cls()

    @staticmethod
    def _backup_corrupt_file(path: str) -> None:
        try:
            if not path or not os.path.exists(path):
                return
            ts = int(time.time())
            backup_path = f"{path}.corrupt.{ts}"
            os.replace(path, backup_path)
            logger.warning("Backed up corrupt blockchain file to %s", backup_path)
        except Exception as e:
            logger.error("Failed to backup corrupt blockchain file: %s", e)

    def to_dict(self) -> dict:
        return {
            "length": len(self.chain),
            "valid": self.validate_chain(),
            "last_block": {
                "index": self.last_block.index,
                "hash": self.last_block.hash,
                "previous_hash": self.last_block.previous_hash,
                "timestamp": self.last_block.timestamp,
                "transaction_count": len(self.last_block.transactions),
            },
        }
