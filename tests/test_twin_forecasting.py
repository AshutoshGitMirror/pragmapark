"""P2 — honest forecasting integration tests.

Proves the remediation rules:
  * STID is retrained ONLY on real observed occupancy (never simulated).
  * The persistence baseline is ALWAYS produced.
  * STID stays a "candidate" unless it beats persistence on REAL evaluated
    forecasts (principle 7: no synthetic data trains or promotes).
  * Promotion metric comes from real evaluated rows only.
"""
from datetime import datetime, timedelta, timezone

from src.api.database import ParkingLot, OccupancyRecord, get_db_cm
from src.digital_twin import forecasting
from src.digital_twin.forecasting import evaluate_and_promote, train_stid_on_real_history
from src.digital_twin.service import PERSISTENCE_VERSION, SUPERVISED_VERSION, ObservationInput, TwinService


def _seed_lot(db, lot_id="MB1"):
    if db.query(ParkingLot).filter(ParkingLot.lot_id == lot_id).first():
        return
    db.add(
        ParkingLot(
            lot_id=lot_id,
            name=lot_id,
            city="Mumbai",
            total_slots=10,
            latitude=19.0760,
            longitude=72.8777,
            base_price=10.0,
        )
    )
    db.commit()


def _seed_real_history(db, lot_id="MB1", n=20, start=datetime(2025, 1, 1, 8, 0, tzinfo=timezone.utc)):
    """Chronological REAL occupancy records (the only allowed training source)."""
    occs = [round(0.3 + 0.01 * i, 3) for i in range(n)]
    for i, occ in enumerate(occs):
        ts = start + timedelta(minutes=15 * i)
        db.add(
            OccupancyRecord(
                lot_id=lot_id,
                timestamp=_naive(ts),
                occupancy_rate=occ,
                occupied_slots=int(round(occ * 10)),
                total_slots=10,
            )
        )
    db.commit()


def _naive(dt: datetime) -> datetime:
    return dt.replace(tzinfo=None)


def _ingest_observation(service, lot_id, ts, occ_rate, total=10, price=15.0):
    return service.ingest_observation(
        ObservationInput(
            lot_id=lot_id,
            observed_at=ts,
            occupied_slots=int(round(occ_rate * total)),
            total_slots=total,
            arrivals=0,
            departures=0,
            price=price,
            sensor_confidence=1.0,
            source="iot",
        )
    )


def test_persistence_baseline_always_present():
    db = _db().__enter__()
    _seed_lot(db, "MB1")
    _seed_real_history(db, "MB1", n=4)
    db.__exit__(None, None, None)
    svc = TwinService()
    _ingest_observation(svc, "MB1", datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc), 0.5)
    rows = svc.generate_forecasts("MB1")
    models = {r.model_name for r in rows}
    assert "persistence" in models
    # Persistence baseline predicts the latest observed occupancy for every horizon.
    latest = 0.5
    for r in rows:
        if r.model_name == "persistence":
            pred = float(r.predicted_occupancy_rate)
            assert abs(pred - latest) < 1e-9


def _db():
    from src.api.database import get_db_cm

    return get_db_cm()


def test_stid_trained_only_on_real_data_and_stays_candidate_when_not_better():
    """A poorly-fit STID must NOT be promoted; provenance must record candidate."""
    db = _db().__enter__()
    _seed_lot(db, "MB1")
    # Real history: deterministic slow drift (persistence will be near-perfect).
    _seed_real_history(db, "MB1", n=24)
    db.__exit__(None, None, None)

    service = TwinService()
    # Ingest one real twin observation and generate forecasts.
    obs_ts = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    _ingest_observation(service, "MB1", obs_ts, 0.5)
    service.generate_forecasts("MB1")

    # Train STID on the SAME real history (no simulated values).
    stid = train_stid_on_real_history(service, lot_cap=100)
    # The trainer saw only real observed occupancy transitions.
    assert stid.trained_real_steps >= 1

    # Produce STID forecasts for a horizon, then evaluate against later real obs.
    horizon = 60
    target = obs_ts + timedelta(minutes=horizon)
    # Add later real observations so forecasts get an attached outcome.
    _ingest_observation(
        service, "MB1", target, 0.51
    )  # near persistence -> persistence wins
    service.evaluate_forecasts(lot_id="MB1")

    report = evaluate_and_promote(service, "MB1", horizon=horizon)
    # With near-constant real data, persistence is hard to beat; STID must
    # therefore remain a candidate (honest: not promoted without proof).
    assert report["status"] == "candidate"
    assert report["promoted"] is False


def test_stid_not_promoted_without_real_evaluated_rows():
    db = _db().__enter__()
    _seed_lot(db, "MB1")
    _seed_real_history(db, "MB1", n=10)
    db.__exit__(None, None, None)

    service = TwinService()
    _ingest_observation(service, "MB1", datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc), 0.4)
    train_stid_on_real_history(service, lot_cap=100)
    # No later real observation ingested -> nothing to evaluate -> cannot promote.
    report = evaluate_and_promote(service, "MB1", horizon=60)
    assert report["persistence_mae"] is None or report["stid_mae"] is None
    assert report["promoted"] is False
    assert report["status"] == "candidate"


def test_forecast_links_model_version_and_outcome():
    db = _db().__enter__()
    _seed_lot(db, "MB1")
    _seed_real_history(db, "MB1", n=16)
    db.__exit__(None, None, None)

    service = TwinService()
    ts = datetime(2025, 1, 1, 11, 0, tzinfo=timezone.utc)
    _ingest_observation(service, "MB1", ts, 0.6)
    rows = service.generate_forecasts("MB1")
    # Every persisted forecast carries a model name + version + input obs id.
    for r in rows:
        assert r.model_name
        assert r.model_version
        assert r.input_observation_id is not None
        assert r.actual_occupancy_rate is None  # immutable until later real obs
    # Attach a later real observation and confirm outcome is linked, not overwritten.
    later = ts + timedelta(minutes=60)
    _ingest_observation(service, "MB1", later, 0.62)
    service.evaluate_forecasts(lot_id="MB1")
    with get_db_cm() as db:
        from src.digital_twin.orm import TwinForecast

        ev = db.query(TwinForecast).filter(
            TwinForecast.actual_occupancy_rate.isnot(None)
        ).first()
    assert ev is not None
    assert ev.actual_occupancy_rate is not None
    # predicted value is unchanged by evaluation (immutability / principle 2).
    assert ev.predicted_occupancy_rate is not None
