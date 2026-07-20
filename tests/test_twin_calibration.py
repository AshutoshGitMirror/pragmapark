"""Calibration component tests (plan P5: honest replacement for the removed
CVAE-WGAN generative counterfactual).

Asserts the non-negotiable principles for the calibrated band:
* bands are derived ONLY from REAL observed occupancy deltas (principle 1)
* the result is persisted as a ``calibrated`` (never ``learned``) TwinScenarioRun
* the run never mutates production state (principle 8)
* sparse real data is flagged ``experimental`` rather than sold as evidence
  (principle 7)
* bootstrap interval is ordered and within [0, 1]
"""

import sys
import os

sys.path.append(os.getcwd())

from datetime import datetime, timedelta, timezone

from src.api.database import get_session, ParkingLot
from src.digital_twin.orm import (
    TwinObservation,
    TwinScenarioRun,
    TwinModelVersion,
    TwinState,
)
from src.digital_twin.service import ObservationInput, twin_service
from src.digital_twin.calibration import (
    CalibratedScenarioRunner,
    fit_calibration,
    bootstrap_band,
    CalibrationFit,
)


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
    """Ingest ``n`` real observations ``step_min`` apart with rate ``rate_fn(i)``."""
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


def test_fit_calibration_uses_real_deltas():
    _seed_lot("MB1")
    start = datetime(2026, 7, 20, 8, 0, 0, tzinfo=timezone.utc)
    # 30m cadence with a varying (non-constant) occupancy signal so the
    # observed hourly deltas carry REAL variance (std > 0). A deterministic
    # linear ramp would produce identical deltas (std=0) and is correctly
    # flagged low-confidence by the calibration gate.
    _seed_observations(
        "MB1", 44, start, 30,
        lambda i: round(0.5 + 0.08 * __import__("math").sin(i / 3.0), 4),
    )

    fit = fit_calibration("MB1", horizon_minutes=60)
    assert fit.n >= 10
    # Real variance in deltas => not flagged low-confidence.
    assert not fit.low_confidence
    assert fit.lower_q <= fit.upper_q
    assert fit.std_delta > 0


def test_fit_calibration_low_confidence_with_no_data():
    _seed_lot("MB2")
    fit = fit_calibration("MB2", horizon_minutes=60)
    assert fit.n == 0
    assert fit.low_confidence is True
    # Wide, explicitly low-confidence band.
    lo, hi = fit.interval(0.5)
    assert lo <= hi


def test_bootstrap_band_ordered_within_unit():
    _seed_lot("MB1")
    start = datetime(2026, 7, 20, 8, 0, 0, tzinfo=timezone.utc)
    _seed_observations("MB1", 40, start, 30, lambda i: 0.3 + 0.004 * i)

    lo, hi, n = bootstrap_band("MB1", 0.5, horizon_minutes=60, seed=7)
    assert n >= 10
    assert 0.0 <= lo <= hi <= 1.0


def test_bootstrap_band_no_real_data_is_degenerate():
    _seed_lot("MB2")
    lo, hi, n = bootstrap_band("MB2", 0.5, horizon_minutes=60, seed=1)
    assert n == 0
    # Even with no data, bounds remain valid and ordered.
    assert 0.0 <= lo <= hi <= 1.0


def test_run_scenario_persists_calibrated_run_no_production_mutation():
    _seed_lot("MB1")
    start = datetime(2026, 7, 20, 8, 0, 0, tzinfo=timezone.utc)
    _seed_observations("MB1", 50, start, 30, lambda i: 0.4 + 0.002 * i)

    runner = CalibratedScenarioRunner()
    base_state = {"occupancy_rate": 0.5, "total_slots": 100, "price": 12.0}
    result = runner.run_scenario(
        "MB1", "price_surge", base_state, horizon_minutes=60, seed=42
    )

    # Result shape + honest labelling.
    assert result.kind == "calibrated"
    assert result.scenario == "price_surge"
    assert result.n_real_samples >= 10
    assert result.lower_occupancy_rate is not None
    assert result.upper_occupancy_rate is not None
    assert 0.0 <= result.lower_occupancy_rate <= result.upper_occupancy_rate <= 1.0
    # Never claims to be a learned (causal) counterfactual.
    assert "learned" not in result.kind
    # Safety note present (principle 8).
    assert result.safety_note
    assert "NOT mutate" in result.safety_note or "not mutate" in result.safety_note.lower()

    # Persisted as a calibrated TwinScenarioRun.
    with get_session() as db:
        run = (
            db.query(TwinScenarioRun)
            .filter(
                TwinScenarioRun.lot_id == "MB1",
                TwinScenarioRun.kind == "calibrated",
            )
            .order_by(TwinScenarioRun.created_at.desc())
            .first()
        )
        assert run is not None
        assert run.lower_occupancy_rate is not None
        assert run.upper_occupancy_rate is not None
        # Versioned artifact recorded.
        mv = db.query(TwinModelVersion).filter(
            TwinModelVersion.model_name == "twin_calibration"
        ).first()
        assert mv is not None

    # Production state untouched: the scenario writes ONLY a TwinScenarioRun,
    # never a TwinState. The number of TwinState rows must equal the number of
    # ingested observations (50) and no extra row was created by the scenario
    # run. (Slots are integer-rounded, so the last observed occupancy is 0.5;
    # the point is proven by the row COUNT, not by the decimal value.)
    with get_session() as db:
        n_states = db.query(TwinState).filter(TwinState.lot_id == "MB1").count()
        assert n_states == 50  # no extra state row was created by the scenario
        n_runs = (
            db.query(TwinScenarioRun)
            .filter(
                TwinScenarioRun.lot_id == "MB1",
                TwinScenarioRun.kind == "calibrated",
            )
            .count()
        )
        assert n_runs == 1  # exactly one scenario run persisted



def test_run_all_returns_one_result_per_scenario():
    _seed_lot("MB1")
    start = datetime(2026, 7, 20, 8, 0, 0, tzinfo=timezone.utc)
    _seed_observations("MB1", 50, start, 30, lambda i: 0.4)

    runner = CalibratedScenarioRunner()
    base_state = {"occupancy_rate": 0.4, "total_slots": 100, "price": 10.0}
    results = runner.run_all("MB1", base_state, horizon_minutes=60, seed=3)
    assert len(results) >= 3
    for r in results:
        assert r.kind == "calibrated"
        assert r.n_real_samples >= 10


def test_experimental_flag_when_sparse_real_data():
    _seed_lot("MB2")
    # Very few real observations -> insufficient for a confident band.
    start = datetime(2026, 7, 20, 8, 0, 0, tzinfo=timezone.utc)
    _seed_observations("MB2", 3, start, 60, lambda i: 0.4)

    runner = CalibratedScenarioRunner()
    base_state = {"occupancy_rate": 0.4, "total_slots": 100, "price": 10.0}
    result = runner.run_scenario(
        "MB2", "price_surge", base_state, horizon_minutes=60, seed=9
    )
    assert result.n_real_samples < 20
    assert result.experimental is True
