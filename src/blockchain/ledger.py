import time
import hashlib
import json
from typing import List, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class Block:
    index: int
    timestamp: float
    transactions: List[dict]
    previous_hash: str
    nonce: int = 0
    hash: Optional[str] = None

    def __post_init__(self):
        if self.hash is None:
            self.hash = self.compute_hash()

    def compute_hash(self) -> str:
        raw = f"{self.index}{self.timestamp}{json.dumps(self.transactions, sort_keys=True)}{self.previous_hash}{self.nonce}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def mine(self, difficulty: int = 2) -> None:
        target = "0" * difficulty
        while not self.hash.startswith(target):
            self.nonce += 1
            self.hash = self.compute_hash()


class BlockchainLedger:
    def __init__(self, difficulty: int = 2):
        self.difficulty = difficulty
        self.chain: List[Block] = []
        self.pending_transactions: List[dict] = []
        self._create_genesis()

    def _create_genesis(self) -> None:
        genesis = Block(
            index=0,
            timestamp=time.time(),
            transactions=[{"type": "genesis", "data": "Smart Parking Genesis Block"}],
            previous_hash="0" * 64,
        )
        genesis.mine(self.difficulty)
        self.chain.append(genesis)

    def add_transaction(self, tx: dict) -> int:
        self.pending_transactions.append(tx)
        return self.last_block.index + 1

    def mine_pending(self) -> Block:
        block = Block(
            index=self.last_block.index + 1,
            timestamp=time.time(),
            transactions=self.pending_transactions[:],
            previous_hash=self.last_block.hash,
        )
        block.mine(self.difficulty)
        self.chain.append(block)
        count = len(self.pending_transactions)
        self.pending_transactions = []
        return block

    def validate_chain(self) -> bool:
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]
            if current.hash != current.compute_hash():
                return False
            if current.previous_hash != previous.hash:
                return False
        return True

    def get_balance(self, driver_id: str) -> float:
        balance = 0.0
        for block in self.chain:
            for tx in block.transactions:
                if tx.get("driver_id") == driver_id:
                    if tx.get("action") == "payment":
                        balance -= tx.get("price", 0)
                    elif tx.get("action") == "refund":
                        balance += tx.get("price", 0)
        return balance

    @property
    def last_block(self) -> Block:
        return self.chain[-1]

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
