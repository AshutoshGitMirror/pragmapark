import os
import shutil
import subprocess  # nosec B404
import logging
import time
import threading
from pathlib import Path
from datetime import datetime, timezone

from src.api.database import get_engine

log = logging.getLogger("pragma.time_machine")

_SNAPSHOT_DIR = Path(os.getenv("PRAGMA_SNAPSHOT_DIR", "data/snapshots"))


class TimeMachine:
    """DB snapshot-based time acceleration.

    Before fast-forward: take a snapshot (file copy for SQLite,
    pg_dump for Postgres).
    During fast-forward: generate data normally — future timestamps
    are fine temporarily.
    On reset: restore from snapshot → clock returns to real time,
    all sim data wiped clean.

    The clock is always real time. Speedup only affects background
    generation rate."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.speedup: int = int(os.getenv("PRAGMA_TIME_SPEEDUP", "1"))
        self.is_fast_forwarding: bool = False
        self._snapshot_path: Path | None = None

    def get_sim_time(self) -> datetime:
        """Always returns real time — no override."""
        return datetime.now(timezone.utc)

    @property
    def snapshot_path(self) -> Path | None:
        return self._snapshot_path

    @snapshot_path.setter
    def snapshot_path(self, val: Path | None) -> None:
        self._snapshot_path = val

    def set_speedup(self, new_speedup: int) -> bool:
        """Change generation rate. Auto-snapshots DB before fast-forward."""
        if new_speedup < 1:
            new_speedup = 1
        if new_speedup > 1 and not self.is_fast_forwarding:
            ok = self._take_snapshot()
            if not ok:
                return False
            self.is_fast_forwarding = True
        elif new_speedup <= 1:
            self.is_fast_forwarding = False
        self.speedup = new_speedup
        log.info("event=speedup.set speedup=%d", new_speedup)
        return True

    def _take_snapshot(self) -> bool:
        """Snapshot DB to file before fast-forward."""
        _SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        self._snapshot_path = _SNAPSHOT_DIR / f"snapshot_{int(time.time())}.db"

        db_url = os.getenv("DATABASE_URL", "")
        if "sqlite" in db_url or not db_url:
            db_path = (
                db_url.replace("sqlite:///", "")
                if db_url
                else _find_sqlite_path()
            )
            if not db_path or not os.path.exists(db_path):
                log.warning("event=snapshot.failed reason=db_not_found")
                return False
            # Close existing connections to avoid copying a mid-write DB
            try:
                engine = get_engine()
                engine.dispose()
            except Exception:  # nosec — non-critical cleanup before copy
                pass
            shutil.copy2(db_path, self._snapshot_path)
            log.info("event=snapshot.saved path=%s", self._snapshot_path)
            return True
        else:
            # PostgreSQL: pg_dump
            try:
                subprocess.run(  # nosec B603,B607
                    ["pg_dump", db_url, "-f", str(self._snapshot_path)],
                    check=True,
                    capture_output=True,
                    timeout=30,
                )
                log.info("event=snapshot.saved path=%s", self._snapshot_path)
                return True
            except Exception as e:
                log.warning("event=snapshot.failed error=%s", e)
                return False

    def reset_to_real(self) -> bool:
        """Restore DB from snapshot. Returns True on success."""
        if not self._snapshot_path or not self._snapshot_path.exists():
            log.warning("event=reset.failed reason=no_snapshot")
            return False

        db_url = os.getenv("DATABASE_URL", "")
        if "sqlite" in db_url or not db_url:
            db_path = (
                db_url.replace("sqlite:///", "")
                if db_url
                else _find_sqlite_path()
            )
            if not db_path:
                log.warning("event=reset.failed reason=db_not_found")
                return False
            # Close existing connections
            try:
                engine = get_engine()
                engine.dispose()
            except Exception:  # nosec — non-critical cleanup before restore
                pass
            shutil.copy2(self._snapshot_path, db_path)
        else:
            # PostgreSQL: drop and restore
            try:
                subprocess.run(  # nosec B603,B607
                    [
                        "psql",
                        db_url,
                        "-c",
                        "DROP SCHEMA public CASCADE; CREATE SCHEMA public;",
                    ],
                    check=True,
                    capture_output=True,
                    timeout=30,
                )
                subprocess.run(  # nosec B603,B607
                    ["pg_restore", db_url, str(self._snapshot_path)],
                    check=True,
                    capture_output=True,
                    timeout=60,
                )
            except Exception as e:
                log.warning("event=reset.failed error=%s", e)
                return False

        # Clean up snapshot
        try:
            self._snapshot_path.unlink()
        except Exception:  # nosec — file may already be gone
            pass
        self._snapshot_path = None
        self.is_fast_forwarding = False
        self.speedup = 1

        log.info("event=reset.complete")
        return True

    def cleanup_stale_snapshots(self):
        """Remove leftover snapshot files."""
        if _SNAPSHOT_DIR.exists():
            for f in _SNAPSHOT_DIR.glob("snapshot_*"):
                try:
                    f.unlink()
                except Exception:  # nosec — best-effort cleanup
                    pass


def _find_sqlite_path() -> str | None:
    """Find the SQLite DB file from common locations."""
    candidates = [
        "data/pragma.db",
        "../data/pragma.db",
        os.path.join(
            os.path.dirname(__file__), "..", "..", "data", "pragma.db"
        ),
    ]
    for c in candidates:
        if os.path.exists(c):
            return os.path.abspath(c)
    return None


time_machine = TimeMachine()
