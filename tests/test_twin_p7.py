"""P7 — validation & safety tests for the observation-driven twin.

Covers lifecycle, leakage, persistence-after-restart, timing, calibration,
baseline, sparse-data, isolation, and the honesty of scenario persistence.

All timestamps are NAIVE UTC because the database stores naive UTC
(AGENTS.md B35: PG vs SQLite portability). Build times with ``datetime.utcnow()``.
"""

import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.getcwd())

from src.digital_twin.service import (
    ObservationInput,
    TwinService,
    FORECAST_HORIZONS_MIN,
)
from src.digital_twin.orm import (
    TwinObservation,
    TwinState,
    TwinForecast,
    TwinScenarioRun,
    TwinModelVersion,
)
from src.api.database import get_db_cm, get_session, ParkingLot


def _seed_lot(lot_id):
    """Create the parent ParkingLot (FK target) for twin rows."""
    with get_session() as db:
        lot = db.query(ParkingLot).filter(ParkingLot.lot_id == lot_id).first()
        if lot is None:
            lot = ParkingLot(
                lot_id=lot_id,
                name="Test Lot",
                total_slots=200,
                city="Mumbai",
                latitude=19.076,
                longitude=72.877,
                base_price=10.0,
            )
            db.add(lot)
            db.commit()


def _obs(lot_id, minutes_ago, occ, total=200, **kw):
    return ObservationInput(
        lot_id=lot_id,
        observed_at=datetime.utcnow() - timedelta(minutes=minutes_ago),
        occupied_slots=int(occ * total),
        total_slots=total,
        price=kw.get("price", 10.0),
        source=kw.get("source", "iot"),
        sensor_confidence=kw.get("conf", 1.0),
        context=kw.get("context", {}),
    )


def _clear_twin(db, lot_id):
    db.query(TwinForecast).filter(TwinForecast.lot_id == lot_id).delete()
    db.query(TwinState).filter(TwinState.lot_id == lot_id).delete()
    db.query(TwinObservation).filter(TwinObservation.lot_id == lot_id).delete()
    db.query(TwinScenarioRun).filter(TwinScenarioRun.lot_id == lot_id).delete()
    # Ensure the parent ParkingLot (FK target) exists for subsequent writes.
    lot = db.query(ParkingLot).filter(ParkingLot.lot_id == lot_id).first()
    if lot is None:
        lot = ParkingLot(
            lot_id=lot_id,
            name="Test Lot",
            total_slots=200,
            city="Mumbai",
            latitude=19.076,
            longitude=72.877,
            base_price=10.0,
        )
        db.add(lot)
    db.commit()


# ---------------------------------------------------------------- lifecycle
def test_lifecycle_observation_to_metric():
    svc = TwinService()
    lot = "p7_lifecycle"
    with get_db_cm() as db:
        _clear_twin(db, lot)

    # 1. ingest real observation -> derives a TwinState
    o = svc.ingest_observation(_obs(lot, minutes_ago=120, occ=0.40))
    with get_db_cm() as db:
        assert db.query(TwinState).filter(TwinState.lot_id == lot).count() == 1

    # 2. generate forecasts for the standard horizons (15/60/1440)
    rows = svc.generate_forecasts(lot)
    assert len(rows) == 3 * 1  # persistence only -> 3 horizons
    horizons = sorted(r.horizon_minutes for r in rows)
    assert horizons == FORECAST_HORIZONS_MIN
    # every forecast links to its input observation (principle 2)
    assert all(r.input_observation_id == o.id for r in rows)

    # 3. ingest a LATER observation so the short-horizon forecasts can be evaluated
    svc.ingest_observation(_obs(lot, minutes_ago=0, occ=0.55))
    # Only the 15m and 60m horizons have a later observation (the 24h horizon
    # correctly has NO outcome yet -- we never fabricate one).
    matched = svc.evaluate_forecasts(lot)
    assert matched == 2
    with get_db_cm() as db:
        evals = db.query(TwinForecast).filter(
            TwinForecast.lot_id == lot,
            TwinForecast.actual_occupancy_rate.isnot(None),
        ).all()
        # prediction is never overwritten by the outcome
        assert all(abs(r.predicted_occupancy_rate - 0.40) < 1e-9 for r in evals)
        assert all(r.actual_occupancy_rate == 0.55 for r in evals)
        # the 24h forecast legitimately remains unevaluated (no leakage)
        long_fc = db.query(TwinForecast).filter(
            TwinForecast.lot_id == lot,
            TwinForecast.horizon_minutes == 1440,
        ).first()
        assert long_fc.actual_occupancy_rate is None

    # 4. metrics aggregate per (model, version, horizon). Two horizons were
    #    evaluated (15m, 60m) -> two metric groups, each with one sample.
    m = svc.metrics(lot)
    assert len(m) == 2
    horizons_evaluated = sorted(row["horizon_minutes"] for row in m)
    assert horizons_evaluated == [15, 60]
    for row in m:
        assert row["model_name"] == "persistence"
        assert row["n_evaluated"] == 1
        assert row["mae"] == 0.15  # |0.55 - 0.40|

    with get_db_cm() as db:
        _clear_twin(db, lot)


# ------------------------------------------------------------ leakage (P1/P2)
def test_forecast_is_never_retrained_on_later_observation():
    """Principle 1 + P2: a later observation must NOT change an already-written
    forecast. The prediction is immutable; only the outcome columns are added."""
    svc = TwinService()
    lot = "p7_leak"
    with get_db_cm() as db:
        _clear_twin(db, lot)

    svc.ingest_observation(_obs(lot, minutes_ago=60, occ=0.30))
    rows = svc.generate_forecasts(lot)
    before = {r.horizon_minutes: r.predicted_occupancy_rate for r in rows}

    # a wildly different later observation arrives
    svc.ingest_observation(_obs(lot, minutes_ago=0, occ=0.95))
    svc.evaluate_forecasts(lot)

    with get_db_cm() as db:
        after = {
            r.horizon_minutes: r.predicted_occupancy_rate
            for r in db.query(TwinForecast).filter(TwinForecast.lot_id == lot).all()
        }
    assert after == before, "forecast prediction changed after later observation"

    with get_db_cm() as db:
        _clear_twin(db, lot)


# --------------------------------------------------- persistence-after-restart
def test_persistence_after_restart():
    """No singleton/in-memory state (goal: 'No singleton/in-memory-only state').
    Data written by one TwinService instance must be visible to a brand-new
    instance reading from the same DB."""
    lot = "p7_restart"
    with get_db_cm() as db:
        _clear_twin(db, lot)

    svc_a = TwinService()
    # base observation 90 min in the past so both the 15m and 60m forecast
    # targets fall before the "now" observation below.
    svc_a.ingest_observation(_obs(lot, minutes_ago=90, occ=0.5))
    svc_a.generate_forecasts(lot)

    # throw away the instance (simulating a process restart) and make a new one
    del svc_a
    svc_b = TwinService()
    with get_db_cm() as db:
        obs_count = db.query(TwinObservation).filter(
            TwinObservation.lot_id == lot
        ).count()
        fc_count = db.query(TwinForecast).filter(
            TwinForecast.lot_id == lot
        ).count()
    assert obs_count == 1
    assert fc_count == 3
    # the new instance can still generate/evaluate against persisted evidence
    svc_b.ingest_observation(_obs(lot, minutes_ago=0, occ=0.6))
    # 15m + 60m horizons match; 1440 has no later observation yet (honest).
    assert svc_b.evaluate_forecasts(lot) == 2

    with get_db_cm() as db:
        _clear_twin(db, lot)


# ------------------------------------------------------------------- timing
def test_forecast_target_anchored_to_observation_time():
    """Principle 2: forecast horizon target_at must be anchored to the latest
    REAL observation timestamp, not wall-clock.now()."""
    svc = TwinService()
    lot = "p7_timing"
    with get_db_cm() as db:
        _clear_twin(db, lot)

    base = datetime.utcnow() - timedelta(minutes=90)
    svc.ingest_observation(
        ObservationInput(
            lot_id=lot, observed_at=base, occupied_slots=100,
            total_slots=200, price=10.0,
        )
    )
    svc.generate_forecasts(lot)
    with get_db_cm() as db:
        fcs = db.query(TwinForecast).filter(TwinForecast.lot_id == lot).all()
        by_h = {f.horizon_minutes: f.target_at for f in fcs}
    # 15m horizon target == observation time + 15 minutes
    assert abs((by_h[15] - (base + timedelta(minutes=15))).total_seconds()) < 1
    assert abs((by_h[60] - (base + timedelta(minutes=60))).total_seconds()) < 1
    assert abs((by_h[1440] - (base + timedelta(minutes=1440))).total_seconds()) < 1

    with get_db_cm() as db:
        _clear_twin(db, lot)


def test_evaluation_only_matches_first_observation_at_or_after_target():
    svc = TwinService()
    lot = "p7_evalmatch"
    with get_db_cm() as db:
        _clear_twin(db, lot)

    base = datetime.utcnow() - timedelta(minutes=200)
    svc.ingest_observation(
        ObservationInput(lot_id=lot, observed_at=base, occupied_slots=80,
                         total_slots=200, price=10.0)
    )
    svc.generate_forecasts(lot)

    # an observation BEFORE target (should be ignored), one AT target, one after
    svc.ingest_observation(
        ObservationInput(lot_id=lot, observed_at=base + timedelta(minutes=5),
                         occupied_slots=90, total_slots=200, price=10.0)
    )
    at_target = base + timedelta(minutes=15)
    svc.ingest_observation(
        ObservationInput(lot_id=lot, observed_at=at_target, occupied_slots=120,
                         total_slots=200, price=10.0)
    )
    svc.evaluate_forecasts(lot)
    with get_db_cm() as db:
        fc15 = db.query(TwinForecast).filter(
            TwinForecast.lot_id == lot,
            TwinForecast.horizon_minutes == 15,
        ).first()
        # 15-min forecast outcome must come from the observation AT target (0.60)
        assert abs(fc15.actual_occupancy_rate - 0.60) < 1e-9

    with get_db_cm() as db:
        _clear_twin(db, lot)


# -------------------------------------------------------------- calibration
def test_calibration_interval_coverage_reported():
    """Calibration metric (principle 2) is computed from the persisted interval
    bounds and the actual outcome."""
    svc = TwinService()
    lot = "p7_calib"
    with get_db_cm() as db:
        _clear_twin(db, lot)

    svc.ingest_observation(_obs(lot, minutes_ago=60, occ=0.50))
    svc.generate_forecasts(lot)
    # outcome 0.50 falls inside [0.45, 0.55]
    svc.ingest_observation(_obs(lot, minutes_ago=0, occ=0.50))
    svc.evaluate_forecasts(lot)
    m = svc.metrics(lot)
    assert m[0]["interval_coverage"] == 1.0  # all actuals inside the interval

    with get_db_cm() as db:
        _clear_twin(db, lot)


# ----------------------------------------------------------------- baseline
def test_persistence_baseline_always_present():
    """P2: the persistence baseline is always produced so every forecast set has
    an honest, untrained reference for promotion decisions."""
    svc = TwinService()
    lot = "p7_base"
    with get_db_cm() as db:
        _clear_twin(db, lot)

    svc.ingest_observation(_obs(lot, minutes_ago=10, occ=0.42))
    rows = svc.generate_forecasts(lot)
    assert any(r.model_name == "persistence" for r in rows)
    mv = svc.register_model_version(
        model_name="persistence", artifact_version="persistence_v1",
        is_baseline=True, validation_metrics={"note": "deterministic reference"},
    )
    assert mv.is_baseline is True
    with get_db_cm() as db:
        assert db.query(TwinModelVersion).filter(
            TwinModelVersion.model_name == "persistence"
        ).count() == 1

    with get_db_cm() as db:
        _clear_twin(db, lot)


# -------------------------------------------------------------- sparse-data
def test_sparse_data_no_observations_does_not_crash():
    """Principle 7: with no real data there is nothing to forecast and the
    service degrades gracefully (returns []), never inventing synthetic input."""
    svc = TwinService()
    lot = "p7_sparse"
    with get_db_cm() as db:
        _clear_twin(db, lot)

    assert svc.generate_forecasts(lot) == []
    assert svc.evaluate_forecasts(lot) == 0
    assert svc.metrics(lot) == []

    with get_db_cm() as db:
        _clear_twin(db, lot)


def test_sparse_data_single_observation_yields_unevaluated_forecast():
    """A single observation lets us forecast but there is no later outcome yet,
    so metrics must be empty (we do not fabricate errors)."""
    svc = TwinService()
    lot = "p7_sparse2"
    with get_db_cm() as db:
        _clear_twin(db, lot)

    svc.ingest_observation(_obs(lot, minutes_ago=5, occ=0.3))
    rows = svc.generate_forecasts(lot)
    assert len(rows) == 3
    assert svc.evaluate_forecasts(lot) == 0  # no later obs to match
    assert svc.metrics(lot) == []

    with get_db_cm() as db:
        _clear_twin(db, lot)


# --------------------------------------------------------------- isolation
def test_lot_isolation():
    """Forecasts/metrics are scoped per lot; lot A's outcome must not bleed into
    lot B's evaluation."""
    svc = TwinService()
    la, lb = "p7_isoA", "p7_isoB"
    with get_db_cm() as db:
        _clear_twin(db, la)
        _clear_twin(db, lb)

    svc.ingest_observation(_obs(la, minutes_ago=60, occ=0.20))
    svc.ingest_observation(_obs(lb, minutes_ago=60, occ=0.80))
    svc.generate_forecasts(la)
    svc.generate_forecasts(lb)
    # only lot A gets a later observation
    svc.ingest_observation(_obs(la, minutes_ago=0, occ=0.25))
    assert svc.evaluate_forecasts(la) == 2  # 15m + 60m matched; 1440 pending
    assert svc.evaluate_forecasts(lb) == 0  # lot B still has no outcome

    ma = svc.metrics(la)
    mb = svc.metrics(lb)
    # metrics are grouped by (model_name, model_version, horizon_minutes), so
    # the two matched horizons (15m, 60m) produce two rows, both for lot A.
    assert len(ma) == 2 and all(m["lot_id"] == la for m in ma)
    assert mb == []

    with get_db_cm() as db:
        _clear_twin(db, la)
        _clear_twin(db, lb)


# ------------------------------------------------------- scenario honesty (P4/P8)
def test_scenario_run_persists_kind_and_never_mutates_prod():
    """P4 + P8: a persisted TwinScenarioRun records its deterministic kind and
    carries the safety note; persisting it does NOT change TwinState/prod."""
    svc = TwinService()
    lot = "p7_scen"
    with get_db_cm() as db:
        _clear_twin(db, lot)
        svc.ingest_observation(_obs(lot, minutes_ago=5, occ=0.5))

    run = svc.persist_scenario_run(
        lot_id=lot,
        scenario_type="zone_closure",
        kind="deterministic",
        predicted_occupancy_rate=0.95,
        assumptions="closure removes supply",
        uncertainty_note="rule-based, no uncertainty quantification",
        safety_note="recommendation only; does not mutate production",
    )
    with get_db_cm() as db:
        got = db.query(TwinScenarioRun).filter(
            TwinScenarioRun.id == run.id
        ).first()
        assert got.kind == "deterministic"
        assert got.safety_note
        # production state untouched
        st = db.query(TwinState).filter(TwinState.lot_id == lot).first()
        assert st.est_occupancy_rate == 0.5  # unchanged from the observation

    with get_db_cm() as db:
        _clear_twin(db, lot)


def test_forecast_links_input_observation_for_audit():
    """Principle 2: each forecast references the exact observation it was
    generated from, enabling full auditability of the evidence chain."""
    svc = TwinService()
    lot = "p7_audit"
    with get_db_cm() as db:
        _clear_twin(db, lot)

    o = svc.ingest_observation(_obs(lot, minutes_ago=45, occ=0.33))
    svc.generate_forecasts(lot)
    with get_db_cm() as db:
        fcs = db.query(TwinForecast).filter(TwinForecast.lot_id == lot).all()
        obs_ids = {f.input_observation_id for f in fcs}
        assert obs_ids == {o.id}

    with get_db_cm() as db:
        _clear_twin(db, lot)
