import json
import hashlib
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class IPFSContent:
    cid: str
    data: dict
    content_type: str
    timestamp: float
    size_bytes: int


class IPFSOffChainStore:
    def __init__(self):
        self._store: Dict[str, IPFSContent] = {}
        self._pinned: set = set()

    def _compute_cid(self, data: dict) -> str:
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]

    def pin(self, data: dict, content_type: str = "generic") -> str:
        cid = self._compute_cid(data)
        if cid not in self._store:
            self._store[cid] = IPFSContent(
                cid=cid,
                data=data,
                content_type=content_type,
                timestamp=time.time(),
                size_bytes=len(json.dumps(data, default=str)),
            )
        self._pinned.add(cid)
        return cid

    def get(self, cid: str) -> Optional[dict]:
        content = self._store.get(cid)
        return content.data if content else None

    def get_metadata(self, cid: str) -> Optional[dict]:
        content = self._store.get(cid)
        if content is None:
            return None
        return asdict(content)

    def pin_lot_metadata(self, lot_id: str, capacity: int, location: dict, owner: str) -> str:
        metadata = {
            "lot_id": lot_id,
            "capacity": capacity,
            "location": location,
            "owner": owner,
            "timestamp": time.time(),
        }
        return self.pin(metadata, "lot_metadata")

    def pin_allocation_batch(self, lot_id: str, allocations: List[dict]) -> str:
        batch = {
            "lot_id": lot_id,
            "allocations": allocations,
            "timestamp": time.time(),
            "batch_id": hashlib.sha256(str(time.time()).encode()).hexdigest()[:8],
        }
        return self.pin(batch, "allocation_batch")

    def pin_revenue_batch(self, period: str, records: List[dict]) -> str:
        batch = {
            "period": period,
            "records": records,
            "timestamp": time.time(),
            "total": sum(r.get("price", 0) for r in records),
        }
        return self.pin(batch, "revenue_batch")

    def pin_price_history(self, zone_id: str, history: List[dict]) -> str:
        payload = {
            "zone_id": zone_id,
            "history": history,
            "timestamp": time.time(),
        }
        return self.pin(payload, "price_history")

    def get_onchain_tx_payload(self, cid: str) -> dict:
        content = self._store.get(cid)
        if content is None:
            return {"error": "cid not found"}
        return {
            "type": "ipfs_ref",
            "cid": cid,
            "content_type": content.content_type,
            "size_bytes": content.size_bytes,
            "timestamp": content.timestamp,
            "data_hash": hashlib.sha256(json.dumps(content.data, default=str).encode()).hexdigest()[:16],
        }

    def summary(self) -> dict:
        return {
            "total_pins": len(self._pinned),
            "total_objects": len(self._store),
            "total_size_bytes": sum(c.size_bytes for c in self._store.values()),
            "content_types": list(set(c.content_type for c in self._store.values())),
            "pinned_cids": list(self._pinned),
        }
