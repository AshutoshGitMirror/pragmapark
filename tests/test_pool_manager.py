import os
import tempfile
from src.blockchain.pool_manager import PoolManager


class TestPoolManager:
    def test_constructor_creates_empty(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(b"{}")
            path = f.name
        try:
            pm = PoolManager(path)
            assert len(pm._pools) == 0
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_create_pool(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(b"{}")
            path = f.name
        try:
            pm = PoolManager(path)
            pool = pm.create("pool_1", 50, "city")
            assert pool.pool_id == "pool_1"
            assert pool.total_spots == 50
            assert pool.owner == "city"
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_create_duplicate_raises(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(b"{}")
            path = f.name
        try:
            pm = PoolManager(path)
            pm.create("pool_1", 50, "city")
            try:
                pm.create("pool_1", 60, "city")
                assert False, "should raise"
            except ValueError:
                pass
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_get_returns_none_for_missing(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(b"{}")
            path = f.name
        try:
            pm = PoolManager(path)
            assert pm.get("nonexistent") is None
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_get_returns_created_pool(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(b"{}")
            path = f.name
        try:
            pm = PoolManager(path)
            pm.create("pool_1", 50, "city")
            pool = pm.get("pool_1")
            assert pool is not None
            assert pool.total_spots == 50
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_persist_and_reload(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            pm = PoolManager(path)
            pm.create("pool_1", 50, "city")
            pm2 = PoolManager(path)
            pool = pm2.get("pool_1")
            assert pool is not None
            assert pool.total_spots == 50
            assert pool.owner == "city"
        finally:
            if os.path.exists(path):
                os.unlink(path)
