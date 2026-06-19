import json
import hashlib
import os
import time
import logging
from typing import List, Optional
from collections import OrderedDict
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

MAX_STORE_SIZE = int(os.getenv("IPFS_STORE_MAX_SIZE", "1000"))
IPFS_PERSIST_PATH = os.getenv("IPFS_PERSIST_PATH", "data/ipfs_store.json")


@dataclass
class IPFSContent:
    cid: str
    data: dict
    content_type: str
    timestamp: float
    size_bytes: int


class IPFSOffChainStore:
    def __init__(self, persist_path: str = IPFS_PERSIST_PATH):
        self._store: OrderedDict[str, IPFSContent] = OrderedDict()
        self._pinned: set = set()
        self._persist_path = persist_path
        self._load_persisted()

    def _compute_cid(self, data: dict) -> str:
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:46]

    def pin(self, data: dict, content_type: str = "generic") -> str:
        cid = self._compute_cid(data)
        if cid not in self._store:
            if len(self._store) >= MAX_STORE_SIZE:
                evicted_cid, evicted_content = self._store.popitem(last=False)
                logger.info(
                    "EVICT cid=%s type=%s size=%d",
                    evicted_cid,
                    evicted_content.content_type,
                    evicted_content.size_bytes,
                )
            self._store[cid] = IPFSContent(
                cid=cid,
                data=data,
                content_type=content_type,
                timestamp=time.time(),
                size_bytes=len(json.dumps(data, default=str)),
            )
        self._pinned.add(cid)
        self._save_persisted()
        return cid

    def get(self, cid: str) -> Optional[dict]:
        content = self._store.get(cid)
        return content.data if content else None

    def pin_lot_metadata(
        self, lot_id: str, capacity: int, location: dict, owner: str
    ) -> str:
        metadata = {
            "lot_id": lot_id,
            "capacity": capacity,
            "location": location,
            "owner": owner,
            "timestamp": time.time(),
        }
        return self.pin(metadata, "lot_metadata")

    def pin_price_history(self, zone_id: str, history: List[dict]) -> str:
        payload = {
            "zone_id": zone_id,
            "history": history,
            "timestamp": time.time(),
        }
        return self.pin(payload, "price_history")

    def _load_persisted(self) -> None:
        try:
            if not os.path.exists(self._persist_path):
                return
            with open(self._persist_path) as f:
                data = json.load(f)
            for item in data.get("store", []):
                cid = item["cid"]
                content = IPFSContent(**item)
                self._store[cid] = content
            self._pinned = set(data.get("pinned", []))
            logger.info(
                "event=ipfs.persist.load cids=%d path=%s",
                len(self._store),
                self._persist_path,
            )
        except Exception as e:
            logger.warning("event=ipfs.persist.load_failed error=%s", e)

    def _save_persisted(self) -> None:
        try:
            os.makedirs(
                os.path.dirname(self._persist_path) or ".", exist_ok=True
            )
            data = {
                "store": [asdict(c) for c in self._store.values()],
                "pinned": list(self._pinned),
            }
            tmp = self._persist_path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(data, f, indent=2, default=str)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self._persist_path)
        except Exception as e:
            logger.warning("event=ipfs.persist.save_failed error=%s", e)

    def summary(self) -> dict:
        return {
            "total_pins": len(self._pinned),
            "total_objects": len(self._store),
            "total_size_bytes": sum(
                c.size_bytes for c in self._store.values()
            ),
            "content_types": list(
                set(c.content_type for c in self._store.values())
            ),
            "pinned_cids": list(self._pinned),
        }
