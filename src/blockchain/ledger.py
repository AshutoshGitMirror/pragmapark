import numpy as np
import hashlib
from datetime import datetime, timezone
from collections import deque


class BlockchainLedger:
    def __init__(self, difficulty: int = 4):
        self.chain = []
        self.pending_transactions = []
        self.difficulty = difficulty
        self._create_genesis()

    def _create_genesis(self):
        genesis = {
            "index": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "transactions": [],
            "previous_hash": "0" * 64,
            "hash": None,
        }
        genesis["hash"] = self._proof_of_work(genesis)
        self.chain.append(genesis)

    def _proof_of_work(self, block: dict) -> str:
        nonce = 0
        while True:
            data = f"{block['index']}{block['timestamp']}{block['transactions']}{block['previous_hash']}{nonce}"
            h = hashlib.sha256(data.encode()).hexdigest()
            if h.startswith("0" * self.difficulty):
                return h
            nonce += 1

    def add_transaction(self, tx: dict):
        self.pending_transactions.append(tx)

    def mine_pending(self):
        if not self.pending_transactions:
            return
        block = {
            "index": len(self.chain),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "transactions": self.pending_transactions[:],
            "previous_hash": self.chain[-1]["hash"],
            "hash": None,
        }
        block["hash"] = self._proof_of_work(block)
        self.chain.append(block)
        self.pending_transactions = []

    def is_chain_valid(self) -> bool:
        for i in range(1, len(self.chain)):
            prev = self.chain[i - 1]
            curr = self.chain[i]
            if curr["previous_hash"] != prev["hash"]:
                return False
        return True


class IPFSOffChainStore:
    """In-memory IPFS simulator."""
    def __init__(self):
        self.store = {}

    def pin(self, data: dict, namespace: str = "default") -> str:
        cid = hashlib.sha256(str(data).encode()).hexdigest()[:16]
        self.store[cid] = data
        return cid

    def get(self, cid: str) -> dict:
        return self.store.get(cid, {})
