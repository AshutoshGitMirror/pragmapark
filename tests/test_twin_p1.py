"""P1 validation + safety tests for the observation-driven digital twin.

These tests cover the NEW persisted twin path (TwinObservation / TwinState /
TwinForecast / TwinScenarioRun / TwinModelVersion) and assert the non-negotiable
principles directly:
* observations carry a real UTC timestamp
* forecasts span 15m / 60m / 24h
* state is persisted on ingestion
* forecasts are immutable (later outcome attached, never overwritten)
* evaluation matches a LATER real observation (no leakage / no self-training)
* scenario runs never mutate production rows
* persistence survives a "restart" (DB holds the data, no in-memory singleton)

The legacy simulator (``src/digital_twin/simulator.py``) is NOT used here.
"""

import sys
import os

sys.path.append(os.getcwd())

from datetime import datetime, timedelta, timezone

from src.api.database import Base, get_session, get_engine, ParkingLot
from src.digital_twin.orm import (
    TwinObservation,
    TwinState,
    TwinForecast,
    TwinScenarioRun,
    TwinModelVersion,
)
from src.digital_twin.service import ObservationInput, twin_service, FORECAST_HORIZONS_MIN


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


def test_observation_carries_utc_timestamp():
    _seed_lot("MB1")
    t = datetime(2026, 7, 20, 9, 0, 0, tzinfo=timezone.utc)
    obs = twin_service.ingest_observation(
        ObservationInput(
            lot_id="MB1", observed_at=t, occupied_slots=40, total_slots=100
        )
    )
    assert obs.id is not None
    # Stored without tzinfo but represents UTC (principle: UTC ts).
    assert obs.observed_at.year == 2026
    assert obs.observed_at.hour == 9
    assert obs.occupancy_rate == 0.4


def test_state_persisted_on_ingestion():
    _seed_lot("MB1")
    t = datetime(2026, 7, 20, 9, 0, 0, tzinfo=timezone.utc)
    twin_service.ingest_observation(
        ObservationInput(
            lot_id="MB1", observed_at=t, occupied_slots=55, total_slots=100,
            price=12.0, sensor_confidence=0.9,
        )
    )
    with get_session() as db:
        st = (
            db.query(TwinState)
            .filter(TwinState.lot_id == "MB1")
            .order_by(TwinState.state_at.desc())
            .first()
        )
        assert st is not None
        assert st.est_occupancy_rate == 0.55
        assert st.est_available_slots == 45
        assert st.est_price == 12.0
        assert st.source_observation_id is not None


def test_forecast_horizons_generated():
    _seed_lot("MB1")
    t = datetime(2026, 7, 20, 9, 0, 0, tzinfo=timezone.utc)
    twin_service.ingest_observation(
        ObservationInput(
            lot_id="MB1", observed_at=t, occupied_slots=40, total_slots=100
        )
    )
    rows = twin_service.generate_forecasts(lot_id="MB1", as_of=t)
    horizons = sorted({r.horizon_minutes for r in rows})
    assert horizons == sorted(FORECAST_HORIZONS_MIN)
    # Each horizon has a persistence baseline row.
    for h in FORECAST_HORIZONS_MIN:
        matching = [r for r in rows if r.horizon_minutes == h]
        assert len(matching) == 1
        assert matching[0].model_name == "persistence"
        # target_at = as_of + horizon (stored as naive UTC, matching the
        # rest of the codebase which strips tzinfo for PG/SQLite parity).
        expected = (t + timedelta(minutes=h)).replace(tzinfo=None)
        assert matching[0].target_at == expected
        # Links to observed input + model version + horizon (principle 2).
        assert matching[0].input_observation_id is not None
        assert matching[0].model_version
        assert matching[0].generated_at == t.replace(tzinfo=None)


def test_forecast_immutable_outcome_attached_not_overwritten():
    _seed_lot("MB1")
    t0 = datetime(2026, 7, 20, 9, 0, 0, tzinfo=timezone.utc)
    twin_service.ingest_observation(
        ObservationInput(
            lot_id="MB1", observed_at=t0, occupied_slots=40, total_slots=100
        )
    )
    rows = twin_service.generate_forecasts(lot_id="MB1", as_of=t0)
    fc_15 = [r for r in rows if r.horizon_minutes == 15][0]
    original_pred = fc_15.predicted_occupancy_rate

    # Later real observation (the true outcome).
    t1 = t0 + timedelta(minutes=15)
    twin_service.ingest_observation(
        ObservationInput(
            lot_id="MB1", observed_at=t1, occupied_slots=70, total_slots=100
        )
    )
    matched = twin_service.evaluate_forecasts(lot_id="MB1")
    assert matched >= 1

    with get_session() as db:
        fc = db.query(TwinForecast).filter(TwinForecast.id == fc_15.id).first()
        # Outcome attached.
        assert fc.actual_occupancy_rate == 0.7
        assert fc.evaluated_at is not None
        assert fc.error == round(0.7 - original_pred, 6)
        # Prediction is NEVER overwritten.
        assert fc.predicted_occupancy_rate == original_pred

    # Re-evaluating must not change / double-count (immutability).
    matched2 = twin_service.evaluate_forecasts(lot_id="MB1")
    assert matched2 == 0


def test_evaluation_matches_only_later_observation_no_leakage():
    _seed_lot("MB1")
    t0 = datetime(2026, 7, 20, 9, 0, 0, tzinfo=timezone.utc)
    twin_service.ingest_observation(
        ObservationInput(
            lot_id="MB1", observed_at=t0, occupied_slots=40, total_slots=100
        )
    )
    twin_service.generate_forecasts(lot_id="MB1", as_of=t0)

    # Observation BEFORE the 60m target must NOT be used for the 60m forecast.
    t_early = t0 + timedelta(minutes=10)
    twin_service.ingest_observation(
        ObservationInput(
            lot_id="MB1", observed_at=t_early, occupied_slots=99, total_slots=100
        )
    )
    # Real outcome at/after 60m target.
    t_late = t0 + timedelta(minutes=60)
    twin_service.ingest_observation(
        ObservationInput(
            lot_id="MB1", observed_at=t_late, occupied_slots=20, total_slots=100
        )
    )
    twin_service.evaluate_forecasts(lot_id="MB1")

    with get_session() as db:
        fc60 = (
            db.query(TwinForecast)
            .filter(
                TwinForecast.lot_id == "MB1",
                TwinForecast.horizon_minutes == 60,
            )
            .first()
        )
        # Must match the LATER observation (0.2), not the early one (0.99).
        assert fc60.actual_occupancy_rate == 0.2


def test_metrics_computed_per_horizon_and_model():
    _seed_lot("MB1")
    t0 = datetime(2026, 7, 20, 9, 0, 0, tzinfo=timezone.utc)
    twin_service.ingest_observation(
        ObservationInput(
            lot_id="MB1", observed_at=t0, occupied_slots=40, total_slots=100
        )
    )
    twin_service.generate_forecasts(lot_id="MB1", as_of=t0)
    for k in range(1, 4):
        tk = t0 + timedelta(minutes=15 * k)
        twin_service.ingest_observation(
            ObservationInput(
                lot_id="MB1", observed_at=tk, occupied_slots=40, total_slots=100
            )
        )
    twin_service.evaluate_forecasts(lot_id="MB1")
    rows = twin_service.metrics(lot_id="MB1")
    assert len(rows) >= 1
    for r in rows:
        assert "mae" in r and "rmse" in r and "bias" in r
        assert r["model_name"] == "persistence"
        assert r["horizon_minutes"] in FORECAST_HORIZONS_MIN


def test_scenario_run_never_mutates_production():
    _seed_lot("MB1")
    t0 = datetime(2026, 7, 20, 9, 0, 0, tzinfo=timezone.utc)
    twin_service.ingest_observation(
        ObservationInput(
            lot_id="MB1", observed_at=t0, occupied_slots=40, total_slots=100
        )
    )
    run = twin_service.persist_scenario_run(
        lot_id="MB1",
        scenario_type="price_surge",
        kind="deterministic",
        predicted_occupancy_rate=0.5,
        predicted_price=20.0,
        assumptions="Assume 50% price increase.",
        uncertainty_note="Rule-based; no uncertainty quantification.",
    )
    assert run.id is not None
    assert run.kind == "deterministic"
    assert "does not mutate" in run.safety_note

    # Production state must be unchanged by the scenario run.
    with get_session() as db:
        st = (
            db.query(TwinState)
            .filter(TwinState.lot_id == "MB1")
            .order_by(TwinState.state_at.desc())
            .first()
        )
        assert st.est_occupancy_rate == 0.4  # unchanged from observation
        # no scenario row altered the occupancy/price of any production table
        assert db.query(TwinObservation).filter(
            TwinObservation.lot_id == "MB1"
        ).count() == 1


def test_model_version_provenance_persisted():
    mv = twin_service.register_model_version(
        model_name="persistence",
        artifact_version="persistence_v1",
        is_baseline=True,
        validation_metrics={"mae_15m": 0.02},
    )
    assert mv.id is not None
    assert mv.is_baseline is True
    with get_session() as db:
        stored = db.query(TwinModelVersion).filter(
            TwinModelVersion.id == mv.id
        ).first()
        assert stored is not None
        assert "mae_15m" in stored.validation_metrics


def test_persistence_after_restart():
    """Data is in the DB, not an in-memory singleton. A fresh service instance
    (simulating a restart) must still read the persisted observations/forecasts."""
    _seed_lot("MB1")
    t0 = datetime(2026, 7, 20, 9, 0, 0, tzinfo=timezone.utc)
    twin_service.ingest_observation(
        ObservationInput(
            lot_id="MB1", observed_at=t0, occupied_slots=40, total_slots=100
        )
    )
    twin_service.generate_forecasts(lot_id="MB1", as_of=t0)

    # Simulate restart: new TwinService instance, fresh module-level state.
    from src.digital_twin.service import TwinService

    fresh = TwinService()
    with get_session() as db:
        assert db.query(TwinObservation).filter(
            TwinObservation.lot_id == "MB1"
        ).count() == 1
        assert db.query(TwinForecast).filter(
            TwinForecast.lot_id == "MB1"
        ).count() == len(FORECAST_HORIZONS_MIN)
    # The fresh service can still derive forecasts from the persisted observation.
    rows = fresh.generate_forecasts(lot_id="MB1", as_of=t0)
    assert len(rows) == len(FORECAST_HORIZONS_MIN)
