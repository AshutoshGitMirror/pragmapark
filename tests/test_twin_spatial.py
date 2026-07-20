"""P3 — real spatial grounding tests.

Verifies that spatial coupling uses REAL coordinates + road/distance data,
never random embeddings, and that nearby lots are coupled more strongly than
unrelated lots. Also checks the persisted sparse adjacency graph survives a
reload (no singleton/in-memory-only state).
"""
import json
import os

import pytest

from src.digital_twin import spatial
from src.digital_twin.spatial import (
    build_adjacency,
    coupling_strength,
    distance_band,
    load_adjacency,
    neighbors,
)


ADJ = spatial.ADJ_PATH


@pytest.fixture(autouse=True)
def _clear_adj(tmp_path, monkeypatch):
    # Use a temp adjacency file so we don't clobber the committed artifact.
    p = tmp_path / "lot_adjacency.json"
    monkeypatch.setattr(spatial, "ADJ_PATH", p)
    yield
    if p.exists():
        p.unlink()


def _seed_lots(db, coords):
    from src.api.database import ParkingLot

    for lid, (lat, lng) in coords.items():
        db.add(
            ParkingLot(
                lot_id=lid,
                name=lid,
                city="Mumbai",
                total_slots=100,
                latitude=lat,
                longitude=lng,
                base_price=10.0,
            )
        )
    db.commit()


def test_distance_band_thresholds():
    assert distance_band(500) == "near"
    assert distance_band(3000) == "mid"
    assert distance_band(8000) == "far"
    assert distance_band(50000) == "unrelated"


def test_nearby_stronger_than_unrelated():
    # Three real lots: two close, one far.
    coords = {
        "MB1": (19.0760, 72.8777),  # Nariman Point
        "MB2": (19.0765, 72.8780),  # ~70 m away (near)
        "MB9": (19.1800, 72.9500),  # far away (~13 km)
    }
    from src.api.database import get_db_cm

    with get_db_cm() as db_session:
        _seed_lots(db_session, coords)
    adj = build_adjacency()
    # Near pair should have an edge; far pair may not (beyond FAR_M).
    assert "MB2" in adj["MB1"]
    near_coupling = coupling_strength("MB1", "MB2")
    far_coupling = coupling_strength("MB1", "MB9")
    assert near_coupling > far_coupling
    # Near coupling should be high (>0.9); far near zero.
    assert near_coupling > 0.9
    assert far_coupling < 0.2


def test_adjacency_persisted_and_reloadable(tmp_path, monkeypatch):
    coords = {
        "MB1": (19.0760, 72.8777),
        "MB2": (19.0765, 72.8780),
    }
    from src.api.database import get_db_cm

    with get_db_cm() as db_session:
        _seed_lots(db_session, coords)
    build_adjacency()
    assert spatial.ADJ_PATH.exists()
    raw = json.loads(spatial.ADJ_PATH.read_text())
    assert "MB1" in raw and "MB2" in raw
    # Reload from disk (no singleton): load_adjacency reads the file.
    reloaded = load_adjacency()
    assert reloaded == raw
    ns = neighbors("MB1")
    assert any(n[0] == "MB2" for n in ns)


def test_spatial_identity_not_random():
    # coupling_strength is deterministic and does not depend on any random
    # embedding. Two calls with the same inputs must match exactly.
    from src.digital_twin.stid import STIDPredictor

    stid = STIDPredictor(num_zones=2, spatial_dim=8, temporal_dim=8)
    stid.set_zone_index(["A", "B"])
    v1 = stid._spatial_identity(0)
    v2 = stid._spatial_identity(0)
    assert (v1 == v2).all()
    # With no adjacency file and no coords, identity is a zero vector (honest
    # "no spatial claim" rather than random noise).
    assert (v1 == 0).all()
