"""Cross-process consistency stress test using multiprocessing.

Verifies that all DB-backed components work correctly when accessed
from multiple processes simultaneously — the --workers > 1 scenario.

Strategy:
- Use conftest's default DB (dynamic DATABASE_URL resolution).
- Override the autouse setup_db fixture to NOT wipe tables (stress test
  manages its own state via the stress_db fixture).
- Seed N worker processes, each with their own DB engine.
- Workers concurrently perform slot state transitions, blockchain ops,
  rate limiting.
- Verify consistency: no double-booked slots, no lost transactions.

Usage:  pytest tests/test_workers_stress.py -x -v
"""

import logging
import os
import sys
import time
import random
from multiprocessing import Process, Queue

import pytest

logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("JWT_SECRET", "xproc-stress-secret-2026")
os.environ.setdefault("PRAGMA_SEED", "42")

import src.api.database as db_mod  # noqa: E402
from sqlalchemy import select, func, delete  # noqa: E402
from src.api.database import (  # noqa: E402
    Base,
    get_engine,
    get_session,
    get_db_cm,
    ParkingLot,
    MicroSlot,
    SlotCurrentState,
    RateLimitWindow,
)
from src.micro.state_engine import SlotState  # noqa: E402
from src.blockchain.ledger import BlockchainLedger  # noqa: E402
from src.pipeline.orchestrator import pipeline  # noqa: E402


# ---------------------------------------------------------------------------
# Worker functions — each runs in a separate process
# ---------------------------------------------------------------------------


def worker_session_starts(
    worker_id: int, queue: Queue, slot_offset: int, n: int
):
    """Worker process: start n concurrent parking sessions (one per slot).

    Uses a private SQLAlchemy engine per process — forked children must
    NOT share the parent's connection pool (PGRES_TUPLES_OK errors).
    """
    import os
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker
    from src.api.database import DB_URL, MicroSlot as MS
    from src.micro.state_engine import SlotStateEngine, SlotState
    from src.blockchain.ledger import BlockchainLedger

    engine = create_engine(DB_URL, echo=False, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    sse = SlotStateEngine()
    bl = BlockchainLedger(difficulty=2)

    results = []
    for i in range(n):
        slot_idx = slot_offset + i + 1
        try:
            with Session() as s:
                slot = (
                    s.execute(
                        select(MS).where(
                            MS.lot_id == "xproc_lot", MS.slot_index == slot_idx
                        )
                    )
                    .scalars()
                    .first()
                )
                if slot is None:
                    results.append({"slot": slot_idx, "status": "no_slot"})
                    continue
                sse.set_state(slot.id, SlotState.OCCUPIED, db=s)
                bl.add_transaction(
                    {
                        "driver_id": f"worker_{worker_id}",
                        "lot_id": "xproc_lot",
                        "action": "session_fee",
                        "price": 10.0,
                        "duration_minutes": 60,
                    },
                    db=s,
                )

            results.append({"slot": slot_idx, "status": "ok"})
        except Exception as e:
            results.append({"slot": slot_idx, "status": f"error: {e}"})

    queue.put(results)


def thread_race_prebook(
    worker_id: int, results: list, idx: int, target_slot: int
):
    """Thread: try to prebook a specific slot using the global state engine.

    Uses threading (not multiprocessing) so the global engine's self._lock
    serializes the prebook calls. Cross-process prebook atomicity requires
    PostgreSQL's row-level locking (SELECT ... FOR UPDATE) — SQLite cannot
    do this."""
    from src.api.database import get_db_cm, MicroSlot as MS
    from src.micro.state_engine import slot_state_engine
    import time as _time

    try:
        with get_db_cm() as s:
            slot = (
                s.execute(
                    select(MS).where(
                        MS.lot_id == "xproc_lot", MS.slot_index == target_slot
                    )
                )
                .scalars()
                .first()
            )
            if slot is None:
                results[idx] = "no_slot"
                return
            ok = slot_state_engine.prebook(
                slot.id, f"pw_{worker_id}", _time.time() + 3600, db=s
            )
            s.commit()
            results[idx] = "won" if ok else "lost"
    except Exception as e:
        import traceback

        traceback.print_exc()
        results[idx] = f"error: {e}"


def worker_mine(queue: Queue):
    """Worker process: try to mine pending blockchain transactions."""
    import os
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

    from src.blockchain.ledger import BlockchainLedger

    bl = BlockchainLedger(difficulty=2)
    try:
        result = bl.mine_pending()
        queue.put({"status": "mined" if result else "no_pending"})
    except Exception as e:
        queue.put({"status": f"error: {e}"})


def worker_rate_limit(queue: Queue, email: str, n: int):
    """Worker process: hammer a rate-limited endpoint.

    Uses a private SQLAlchemy engine per process — forked children must
    NOT share the parent's connection pool (PGRES_TUPLES_OK errors).
    """
    import os
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from src.api.database import DB_URL
    from src.api.utils import DBRateLimiter

    engine = create_engine(DB_URL, echo=False, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    rl = DBRateLimiter(max_calls=3, window=60.0, prefix="xproc")
    results = []
    for _ in range(n):
        with Session() as s:
            ok = rl.check(email, db=s)
            results.append(ok)
    queue.put(results)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCrossProcessConsistency:
    @pytest.fixture(autouse=True)
    def setup_db(self):
        """Override conftest's setup_db to NOT drop/recreate tables.

        conftest's autouse setup_db runs Base.metadata.drop_all() +
        create_all() before every test, which wipes the module-level seeding.
        This override keeps engine lifecycle correct but skips destructive DDL.
        The stress_db fixture handles explicit data seeding."""
        if db_mod._engine is not None:
            db_mod._engine.dispose()
        db_mod._engine = None
        db_mod._Session = None
        engine = get_engine()
        Base.metadata.create_all(bind=engine)
        yield
        engine.dispose()
        db_mod._engine = None
        db_mod._Session = None
        try:
            pipeline.ledger = BlockchainLedger(difficulty=2)
            if pipeline.dt:
                pipeline.dt.zones.clear()
                if hasattr(pipeline.dt, "state_history"):
                    pipeline.dt.state_history.clear()
                if hasattr(pipeline.dt, "zone_id_to_idx"):
                    pipeline.dt.zone_id_to_idx.clear()
        except Exception:
            logger.warning("event=ledger_reset_failed", exc_info=True)

    @pytest.fixture
    def stress_db(self, setup_db):
        """Seed stress DB with 200 slots in xproc_lot."""
        with get_session() as s:
            if (
                not s.execute(
                    select(ParkingLot).where(ParkingLot.lot_id == "xproc_lot")
                )
                .scalars()
                .first()
            ):
                s.add(
                    ParkingLot(
                        lot_id="xproc_lot",
                        name="XProc Stress Lot",
                        total_slots=200,
                        base_price=10.0,
                        price_cap=50.0,
                    )
                )
            if (
                s.execute(
                    select(func.count())
                    .select_from(MicroSlot)
                    .where(MicroSlot.lot_id == "xproc_lot")
                ).scalar()
                == 0
            ):
                for i in range(1, 201):
                    st = (
                        "handicap"
                        if i % 20 == 0
                        else ("ev" if i % 15 == 0 else "regular")
                    )
                    s.add(
                        MicroSlot(
                            lot_id="xproc_lot",
                            slot_index=i,
                            row_label=chr(64 + (i - 1) // 10),
                            position=(i - 1) % 10 + 1,
                            slot_type=st,
                            active=1,
                            base_modifier_score=random.uniform(0, 0.3),
                        )
                    )
            s.commit()

        with get_session() as s:
            s.execute(delete(SlotCurrentState))
            s.commit()
            for i in range(1, 201):
                ms = (
                    s.execute(
                        select(MicroSlot).where(
                            MicroSlot.lot_id == "xproc_lot",
                            MicroSlot.slot_index == i,
                        )
                    )
                    .scalars()
                    .first()
                )
                if ms:
                    existing = (
                        s.execute(
                            select(SlotCurrentState).where(
                                SlotCurrentState.slot_id == ms.id
                            )
                        )
                        .scalars()
                        .first()
                    )
                    if not existing:
                        s.add(
                            SlotCurrentState(
                                slot_id=ms.id,
                                state=SlotState.AVAILABLE,
                                updated_at=time.time(),
                            )
                        )
            s.commit()

        with get_session() as s:
            s.execute(delete(RateLimitWindow))
            s.commit()

        yield

    def _get_engine_pool_size(self):
        """Check how many connections the engine pool has (debug helper)."""
        from src.api.database import get_engine

        e = get_engine()
        return getattr(e.pool, "total", lambda: -1)()

    def test_concurrent_session_starts(self, stress_db):
        """3 worker processes each start 50 sessions (150 total, unique slots).
        All should succeed with no conflicts."""
        N_WORKERS = 3
        SLOTS_PER_WORKER = 50
        queues = [Queue() for _ in range(N_WORKERS)]

        procs = [
            Process(
                target=worker_session_starts,
                args=(i, queues[i], i * SLOTS_PER_WORKER, SLOTS_PER_WORKER),
            )
            for i in range(N_WORKERS)
        ]

        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=60)
        for p in procs:
            if p.is_alive():
                p.terminate()
                p.join()

        # Collect results
        all_results = []
        for q in queues:
            try:
                all_results.extend(q.get(timeout=5))
            except Exception:
                logger.warning(
                    "event=queue_timeout_missed_worker", exc_info=True
                )

        assert len(all_results) == N_WORKERS * SLOTS_PER_WORKER, (
            f"Expected {N_WORKERS * SLOTS_PER_WORKER} results, "
            f"got {len(all_results)}"
        )

        errors = [r for r in all_results if r["status"] != "ok"]
        assert len(errors) == 0, f"{len(errors)} errors: {errors[:5]}"

    def test_race_prebook_same_slot(self, stress_db):
        """10 threads all prebook same slot; exactly 1 should win.
        Uses threading so in-process SlotStateEngine._lock serializes.
        Cross-process prebook atomicity needs PostgreSQL
        (SELECT FOR UPDATE)."""
        import threading

        N = 10
        RACE_SLOT = 170
        results = [None] * N
        threads = [
            threading.Thread(
                target=thread_race_prebook, args=(i, results, i, RACE_SLOT)
            )
            for i in range(N)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        winners = sum(1 for r in results if r == "won")
        losers = sum(1 for r in results if r == "lost")
        errors = [
            r for r in results if r is not None and r.startswith("error")
        ]

        assert winners == 1, (
            f"Expected exactly 1 winner, got {winners}. Results: {results}"
        )
        assert winners + losers == N, (
            f"Expected {N} resolved, got {winners}+{losers}+{len(errors)}"
        )

    def test_concurrent_blockchain_ops(self, stress_db):
        """Multiple worker processes add transactions and mine concurrently."""
        N_WORKERS = 4
        queues = [Queue() for _ in range(N_WORKERS)]

        add_procs = [
            Process(target=self._worker_add_tx, args=(i, queues[i]))
            for i in range(N_WORKERS)
        ]
        for p in add_procs:
            p.start()
        for p in add_procs:
            p.join(timeout=15)

        mine_procs = [
            Process(target=self._worker_mine_bl, args=(i, queues[i]))
            for i in range(N_WORKERS)
        ]
        for p in mine_procs:
            p.start()
        for p in mine_procs:
            p.join(timeout=15)
        for p in mine_procs:
            if p.is_alive():
                p.terminate()

        from src.blockchain.ledger import BlockchainLedger

        bl2 = BlockchainLedger(difficulty=2)
        chain = bl2.chain
        pend = bl2.pending_transactions
        assert len(chain) >= 1, f"Expected at least 1 block, got {len(chain)}"
        assert len(pend) == 0, f"Expected 0 pending, got {len(pend)}"

    @staticmethod
    def _worker_add_tx(worker_id: int, queue: Queue):
        import os
        import sys

        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from src.blockchain.ledger import BlockchainLedger

        bl = BlockchainLedger(difficulty=2)
        bl.add_transaction(
            {
                "driver_id": f"miner_{worker_id}",
                "lot_id": "xproc_lot",
                "action": "session_fee",
                "price": 5.0,
                "duration_minutes": 30,
            }
        )
        queue.put("added")

    @staticmethod
    def _worker_mine_bl(worker_id: int, queue: Queue):
        import os
        import sys

        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from src.blockchain.ledger import BlockchainLedger

        bl = BlockchainLedger(difficulty=2)
        try:
            result = bl.mine_pending()
            queue.put({"status": "mined" if result else "no_pending"})
        except Exception as e:
            queue.put({"status": f"error: {e}"})

    def test_rate_limiter_cross_process(self, stress_db):
        """Hammer a rate limiter from multiple processes concurrently."""
        N_WORKERS = 3
        CALLS_PER_WORKER = 5
        EMAIL = f"xproc_rate_{os.getpid()}@test.io"

        # Clear rate limits first
        with get_db_cm() as s:
            s.execute(delete(RateLimitWindow))
            s.commit()

        queues = [Queue() for _ in range(N_WORKERS)]
        procs = [
            Process(
                target=worker_rate_limit,
                args=(queues[i], EMAIL, CALLS_PER_WORKER),
            )
            for i in range(N_WORKERS)
        ]

        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=30)
        for p in procs:
            if p.is_alive():
                p.terminate()
                p.join()

        all_results = []
        for q in queues:
            try:
                all_results.extend(q.get(timeout=5))
            except Exception:
                logger.warning(
                    "event=rate_limiter_queue_timeout", exc_info=True
                )

        allowed = sum(1 for r in all_results if r is True)
        denied = sum(1 for r in all_results if r is False)
        total = len(all_results)

        assert total == N_WORKERS * CALLS_PER_WORKER, (
            f"Expected {N_WORKERS * CALLS_PER_WORKER} results, got {total}"
        )
        assert denied >= 1, (
            f"Expected >=1 rate-limited call; "
            f"allowed={allowed}, denied={denied}"
        )
        assert allowed <= 3, (
            f"Rate limiter should allow at most 3, got {allowed}"
        )
