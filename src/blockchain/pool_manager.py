import os
import json
import fcntl
import threading
import logging
from src.blockchain import ParkingPool
from src.blockchain.transaction import AllocationRecord

logger = logging.getLogger(__name__)


class PoolManager:
    def __init__(self, path: str | None = None):
        self._pools: dict[str, ParkingPool] = {}
        self._lock = threading.Lock()
        if path is not None:
            self._path: str = path
        else:
            self._path = os.getenv("POOLS_PATH", "data/pools.json")
        self._load()

    def _load(self) -> None:
        logger.info("event=pools.load.received path=%s", self._path)
        try:
            with open(self._path, "r") as f:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                    data = json.load(f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            with self._lock:
                for pool_id, payload in data.items():
                    pool = ParkingPool(
                        pool_id=pool_id,
                        total_spots=int(payload.get("total_spots", 0)),
                        owner=str(payload.get("owner", "city")),
                        on_mutation=self._persist,
                    )
                    allocations = payload.get("allocations", {})
                    for spot_id, alloc in allocations.items():
                        try:
                            pool.allocations[spot_id] = AllocationRecord(**alloc)
                        except (TypeError, ValueError):
                            logger.warning("event=pools.load.alloc_skipped pool=%s spot=%s", pool_id, spot_id)
                            continue
                    pool.revenue_log = list(payload.get("revenue_log", []))
                    self._pools[pool_id] = pool
            logger.info("event=pools.load.completed pools=%d path=%s", len(self._pools), self._path)
        except FileNotFoundError:
            logger.info("event=pools.load.skipped path=%s (not found)", self._path)
        except Exception as e:
            logger.error("event=pools.load.failed path=%s error=%s", self._path, e)

    def _persist(self) -> None:
        logger.info("event=pools.persist.started pools=%d path=%s", len(self._pools), self._path)
        try:
            os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
            with self._lock:
                data = {
                    pid: {
                        "total_spots": pool.total_spots,
                        "owner": pool.owner,
                        "allocations": {k: v.to_dict() for k, v in pool.allocations.items()},
                        "revenue_log": list(pool.revenue_log),
                    }
                    for pid, pool in self._pools.items()
                }
            tmp_path = self._path + ".tmp"
            with open(tmp_path, "w") as f:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    json.dump(data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            os.replace(tmp_path, self._path)
            dir_fd = os.open(os.path.dirname(self._path) or ".", os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
            logger.info("event=pools.persist.completed path=%s", self._path)
        except Exception as e:
            logger.error("event=pools.persist.failed path=%s error=%s", self._path, e)

    def get(self, pool_id: str) -> ParkingPool | None:
        with self._lock:
            return self._pools.get(pool_id)

    def create(self, pool_id: str, total_spots: int, owner: str) -> ParkingPool:
        with self._lock:
            if pool_id in self._pools:
                raise ValueError(f"Pool {pool_id} already exists")
            pool = ParkingPool(pool_id, total_spots, owner, on_mutation=self._persist)
            self._pools[pool_id] = pool
        self._persist()
        return pool


pool_manager = PoolManager()
