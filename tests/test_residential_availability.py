"""Unit tests for the Phase 3 residential availability model.

Replaces the time-of-day stub with a learned Beta-Binomial estimator keyed by
neighborhood spatial bucket + (weekday, hour), trained from observed signals.
No manual schedule is hard-coded anywhere.
"""
from datetime import datetime, timezone

from src.residential import geo
from src.residential.availability import (
    MODEL_PATH,
    NEIGHBORHOOD_PRECISION,
    ResidentialAvailabilityModel,
    residential_availability_model,
)


def _bucket(lat, lng, precision=NEIGHBORHOOD_PRECISION):
    return geo.geohash_encode(lat, lng, precision)


def _records(bucket, wd, hr, n_avail, n_occ):
    recs = []
    for _ in range(n_avail):
        recs.append((bucket, wd, hr, False))
    for _ in range(n_occ):
        recs.append((bucket, wd, hr, True))
    return recs


def test_untrained_predict_is_neutral_and_well_shaped():
    m = ResidentialAvailabilityModel()
    dt = datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc)  # Tuesday
    p = m.predict(19.076, 72.8777, dt=dt)
    assert p["model"] == "residential_beta_binomial"
    assert 0.0 <= p["p_available_now"] <= 1.0
    assert 0.0 <= p["p_available_15m"] <= 1.0
    assert 0.0 <= p["p_available_60m"] <= 1.0


def test_model_learns_availability_from_records():
    m = ResidentialAvailabilityModel()
    bucket = _bucket(19.076, 72.8777)
    # Mostly-available at (bucket, Tuesday 10:00)
    m.train_from_records(_records(bucket, wd=1, hr=10, n_avail=20, n_occ=1))
    dt = datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc)
    p = m.predict(19.076, 72.8777, dt=dt)
    assert p["p_available_15m"] > 0.8
    assert p["p_available_60m"] > 0.8
    # Different time of day has no cell -> falls back to neighborhood/global prior
    dt_night = datetime(2026, 7, 21, 3, 0, tzinfo=timezone.utc)
    p_night = m.predict(19.076, 72.8777, dt=dt_night)
    assert 0.0 <= p_night["p_available_15m"] <= 1.0


def test_occupied_now_lowers_instantaneous_availability():
    m = ResidentialAvailabilityModel()
    bucket = _bucket(19.076, 72.8777)
    m.train_from_records(_records(bucket, wd=1, hr=10, n_avail=20, n_occ=1))
    dt = datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc)
    free = m.predict(19.076, 72.8777, dt=dt, occupied_now=False)
    occ = m.predict(19.076, 72.8777, dt=dt, occupied_now=True)
    assert occ["p_available_now"] < free["p_available_now"]
    assert occ["p_available_now"] <= 0.1


def test_active_share_raises_availability():
    m = ResidentialAvailabilityModel()
    bucket = _bucket(19.076, 72.8777)
    # Train as mostly occupied (low availability baseline)
    m.train_from_records(_records(bucket, wd=1, hr=10, n_avail=1, n_occ=20))
    dt = datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc)
    base = m.predict(19.076, 72.8777, dt=dt, has_active_share=False)
    shared = m.predict(19.076, 72.8777, dt=dt, has_active_share=True)
    assert shared["p_available_15m"] >= max(0.6, base["p_available_15m"])


def test_neighborhood_pooling_fallback_to_bucket():
    # A slot in a trained neighborhood but at an unobserved (weekday, hour)
    # should inherit the neighborhood bucket's stats (spatial/time pooling),
    # not fall back to the neutral global prior.
    m = ResidentialAvailabilityModel()
    bucket = _bucket(19.076, 72.8777)
    m.train_from_records(_records(bucket, wd=1, hr=10, n_avail=25, n_occ=0))
    # Tuesday 03:00 — no cell for this hour, but the bucket is well trained.
    dt = datetime(2026, 7, 21, 3, 0, tzinfo=timezone.utc)
    p = m.predict(19.076, 72.8777, dt=dt)
    assert p["p_available_15m"] > 0.8


def test_save_and_load_round_trip(tmp_path):
    m = ResidentialAvailabilityModel()
    bucket = _bucket(19.076, 72.8777)
    m.train_from_records(_records(bucket, wd=1, hr=10, n_avail=10, n_occ=2))
    path = str(tmp_path / "avail.json")
    m.save(path)
    m2 = ResidentialAvailabilityModel()
    assert m2.load(path) is True
    dt = datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc)
    p1 = m.predict(19.076, 72.8777, dt=dt)
    p2 = m2.predict(19.076, 72.8777, dt=dt)
    assert p1["p_available_15m"] == p2["p_available_15m"]


def test_geo_predict_availability_delegates_to_model():
    # The geo wrapper keeps the same public shape the endpoint/tests expect.
    p = geo.predict_availability(19.076, 72.8777)
    assert "p_available_15m" in p and "p_available_60m" in p
    assert p["model"] == "residential_beta_binomial"
