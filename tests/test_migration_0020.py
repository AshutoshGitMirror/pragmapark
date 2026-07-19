"""Migration 0020 test: add residential geo columns + nullable lot_id + backfill.

Runs alembic via the CLI (same path CI uses) against a throwaway sqlite DB.
"""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = str(ROOT / "alembic.ini")


def _alembic(db_url, revision):
    env = dict(os.environ)
    env["DATABASE_URL"] = db_url
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", ALEMBIC_INI, "upgrade", revision],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.mark.skipif(
    os.environ.get("SKIP_MIGRATION_TESTS") == "1",
    reason="migration tests disabled",
)
def test_migration_0020_sqlite_backfill_and_downgrade(tmp_path):
    db = tmp_path / "m.db"
    url = f"sqlite:///{db}"

    # Build schema up to 0019 (pre-geo).
    r = _alembic(url, "0019")
    assert r.returncode == 0, r.stderr

    # Seed a lot + a lot-attached micro_slot (old schema: lot_id NOT NULL, no lat/lng).
    con = sqlite3.connect(str(db))
    cur = con.cursor()
    cur.execute(
        "INSERT INTO parking_lots (lot_id,name,total_slots,base_price,latitude,longitude) "
        "VALUES ('m1','Lot M',5,10.0,19.01,72.91)"
    )
    cur.execute(
        "INSERT INTO micro_slots (lot_id,slot_index,active) VALUES ('m1',1,1)"
    )
    con.commit()
    con.close()

    # Upgrade to 0020 -> should add cols and backfill lat/lng from the lot.
    r = _alembic(url, "0020")
    assert r.returncode == 0, r.stderr

    con = sqlite3.connect(str(db))
    cur = con.cursor()
    cols = {row[1] for row in cur.execute("PRAGMA table_info(micro_slots)")}
    assert "latitude" in cols and "longitude" in cols
    cur.execute("SELECT latitude,longitude FROM micro_slots WHERE lot_id='m1'")
    row = cur.fetchone()
    con.close()
    assert row is not None
    assert abs(row[0] - 19.01) < 1e-6
    assert abs(row[1] - 72.91) < 1e-6

    # Downgrade back to 0019 should succeed.
    r = _alembic(url, "0019")
    assert r.returncode == 0, r.stderr
