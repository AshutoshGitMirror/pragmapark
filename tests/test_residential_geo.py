"""Unit tests for the residential geospatial helpers (Phase 1)."""
from src.residential import geo


def test_geohash_round_trip():
    lat, lng = 19.0760, 72.8777
    gh = geo.geohash_encode(lat, lng, precision=7)
    assert isinstance(gh, str) and len(gh) == 7
    clat, clng = geo.decode_center(gh)
    # precision-7 cell is ~150m, so the center is within ~0.01 deg
    assert abs(clat - lat) < 0.01
    assert abs(clng - lng) < 0.01


def test_spatial_id_format():
    # spatial_id returns the raw geohash; the "PK_" namespace is added in slot_geo
    gh = geo.spatial_id(19.0760, 72.8777, precision=7)
    assert gh == geo.geohash_encode(19.0760, 72.8777, 7)
    assert not gh.startswith("PK_")


def test_in_mumbai():
    assert geo.in_mumbai(19.0760, 72.8777) is True       # Mumbai proper
    assert geo.in_mumbai(19.20, 72.95) is True            # inside bbox
    assert geo.in_mumbai(28.6139, 77.2090) is False       # Delhi
    assert geo.in_mumbai(20.0, 73.5) is False             # outside bbox (north/east)


def test_slot_geo_standalone():
    g = geo.slot_geo(19.0760, 72.8777)
    assert g["latitude"] == 19.0760
    assert g["longitude"] == 72.8777
    assert g["spatial_id"] == f"PK_{geo.spatial_id(19.0760, 72.8777)}"
    assert g["precision"] == 7


def test_slot_geo_attached():
    g = geo.slot_geo(19.0, 72.9)
    assert g["latitude"] == 19.0
    assert g["longitude"] == 72.9
    assert g["spatial_id"].startswith("PK_")
    assert len(g["spatial_id"]) == 10  # "PK_" + 7-char geohash


def test_predict_availability_keys_and_range():
    p = geo.predict_availability(19.0760, 72.8777)
    assert "p_available_15m" in p and "p_available_60m" in p
    assert 0.0 <= p["p_available_15m"] <= 1.0
    assert 0.0 <= p["p_available_60m"] <= 1.0
