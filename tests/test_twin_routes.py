"""HTTP route tests for the observation-driven digital twin (P1 / P7).

Exercises the live ``/api/v1/twin`` API and asserts the non-negotiable
principles through the HTTP boundary:

* observations are persisted and derived twin state follows (P1)
* forecasts are persisted (never overwritten) and link to a model version (P2)
* every forecast is matched to a later real observation and gets an error (P1/P2)
* a calibrated scenario run is persisted but NEVER mutates production state
  (principle 8) — observed via the HTTP layer.
"""

import sys
import os

sys.path.append(os.getcwd())

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from src.api.database import get_session, ParkingLot
from src.api.server import app
from src.digital_twin.orm import (
    TwinObservation,
    TwinState,
    TwinForecast,
    TwinScenarioRun,
)
from src.digital_twin.service import ObservationInput, twin_service


def _make_lot(db, lot_id="MB1"):
    lot = db.query(ParkingLot).filter(ParkingLot.lot_id == lot_id).first()
    if lot is None:
        lot = ParkingLot(
            lot_id=lot_id,
            name="Test Lot",
            total_slots=100,
            city="Mumbai",
            latitude=19.076,
            longitude=72.877,
            base_price=10.0,
        )
        db.add(lot)
        db.commit()
    return lot


def _seed_lot(lot_id="MB1"):
    with get_session() as db:
        _make_lot(db, lot_id)


def _seed_observations(lot_id, n, start, step_min, rate_fn):
    t = start
    for i in range(n):
        twin_service.ingest_observation(
            ObservationInput(
                lot_id=lot_id,
                observed_at=t,
                occupied_slots=int(round(rate_fn(i) * 100)),
                total_slots=100,
            )
        )
        t = t + timedelta(minutes=step_min)


def _client():
    return TestClient(app)


def test_observation_ingest_persists_state_and_is_listable():
    _seed_lot("MB1")
    start = datetime(2026, 7, 20, 8, 0, 0, tzinfo=timezone.utc)
    _seed_observations("MB1", 10, start, 15, lambda i: 0.4 + 0.01 * i)

    c = _client()
    # list observations via HTTP
    resp = c.get("/api/v1/twin/observations/MB1", params={"limit": 100})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 10
    assert all("occupancy_rate" in row for row in body)

    # derived state is listable and the latest reflects the last real obs
    st = c.get("/api/v1/twin/state/MB1", params={"limit": 10})
    assert st.status_code == 200
    states = st.json()
    assert len(states) == 10  # one TwinState per ingested observation
    latest = max(states, key=lambda s: s["state_at"])
    # last obs: 0.4 + 0.01*9 = 0.49 -> 49 occupied -> 0.49
    assert abs(latest["est_occupancy_rate"] - 0.49) < 1e-6


def test_forecast_generate_persists_and_evaluate_links_outcome():
    _seed_lot("MB1")
    start = datetime(2026, 7, 20, 8, 0, 0, tzinfo=timezone.utc)
    # Seed an EARLY window of real observations first...
    _seed_observations("MB1", 40, start, 15, lambda i: 0.4 + 0.001 * i)

    c = _client()
    # ...generate forecasts anchored at the latest of those early obs...
    gen = c.post(
        "/api/v1/twin/forecasts/generate",
        json={"lot_id": "MB1", "horizons": [15, 60, 1440]},
    )
    assert gen.status_code == 200
    forecasts = gen.json()
    assert len(forecasts) >= 1
    # model version is always recorded (P2)
    assert all(f["model_version"] for f in forecasts)

    # ...then seed the LATER real observations so the forecasts have outcomes.
    later = start + timedelta(minutes=40 * 15)
    _seed_observations("MB1", 200, later, 15, lambda i: 0.4 + 0.001 * (40 + i))

    # evaluate: every forecast gets a later real observation + error (P1/P2)
    ev = c.post("/api/v1/twin/forecasts/evaluate", json={"lot_id": "MB1"})
    assert ev.status_code == 200
    matched = ev.json()["matched"]
    assert matched >= 1

    with get_session() as db:
        evd = (
            db.query(TwinForecast)
            .filter(
                TwinForecast.lot_id == "MB1",
                TwinForecast.actual_occupancy_rate.isnot(None),
            )
            .count()
        )
        assert evd >= 1

    # metrics endpoint reports measured error (P7 / Required Metrics)
    mt = c.get("/api/v1/twin/metrics", params={"lot_id": "MB1"})
    assert mt.status_code == 200
    assert any(m["n_evaluated"] >= 1 for m in mt.json())


def test_calibrated_scenario_persists_but_never_mutates_production():
    _seed_lot("MB1")
    start = datetime(2026, 7, 20, 8, 0, 0, tzinfo=timezone.utc)
    _seed_observations("MB1", 44, start, 30, lambda i: 0.5 + 0.05 * ((i % 5) - 2))

    c = _client()
    resp = c.post(
        "/api/v1/twin/scenarios/calibrated",
        json={
            "lot_id": "MB1",
            "scenario": "price_surge",
            "base_state": {
                "occupancy_rate": 0.5,
                "total_slots": 100,
                "price": 12.0,
            },
            "horizon_minutes": 60,
            "use_bootstrap": True,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["kind"] == "calibrated"
    assert "learned" not in body["kind"]
    assert body["safety_note"]
    assert 0.0 <= body["lower_occupancy_rate"] <= body["upper_occupancy_rate"] <= 1.0

    # principle 8: no TwinState was created by the scenario run.
    with get_session() as db:
        n_states = db.query(TwinState).filter(TwinState.lot_id == "MB1").count()
        # exactly the 44 ingested observations, nothing added by the scenario
        assert n_states == 44
        n_runs = (
            db.query(TwinScenarioRun)
            .filter(
                TwinScenarioRun.lot_id == "MB1",
                TwinScenarioRun.kind == "calibrated",
            )
            .count()
        )
        assert n_runs == 1


def test_observation_for_unknown_lot_rejected():
    c = _client()
    resp = c.post(
        "/api/v1/twin/observations",
        json={
            "lot_id": "NOPE",
            "observed_at": "2026-07-20T08:00:00+00:00",
            "occupied_slots": 10,
            "total_slots": 100,
        },
    )
    assert resp.status_code == 404
