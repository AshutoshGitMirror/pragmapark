"""P1 — observation-driven twin service.

This module is the real data path for the digital twin. It is deliberately
decoupled from the simulator (``src/digital_twin/simulator.py``): observations
come ONLY from real sources (IoT ingress, sessions, manual). No simulated
value ever becomes a forecast target (goal principle 1).

Responsibilities
-------------
* ``ingest_observation`` — persist a real ``TwinObservation`` (UTC ts).
* ``update_state`` — derive a durable ``TwinState`` from the latest observation.
* ``generate_forecasts`` — produce horizon forecasts (15m/60m/24h) and
  persist them as immutable ``TwinForecast`` rows. The later observed outcome
  is attached by ``evaluate_forecasts`` and NEVER overwrites the prediction.
* ``evaluate_forecasts`` — match each forecast to the first real observation at or
  after its ``target_at`` and compute signed/abs error.

Forecasting model: the **persistence baseline** is always produced (deterministic,
honest, needs no training). A supervised model registered via
``register_model`` can also be used; it is only ever fed REAL targets when trained
elsewhere. This module never trains a model; it only persists predictions + errors.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from sqlalchemy import and_

from src.api.database import get_db_cm
from src.digital_twin.orm import (
    TwinForecast,
    TwinModelVersion,
    TwinObservation,
    TwinScenarioRun,
    TwinState,
)

logger = logging.getLogger(__name__)


FORECAST_HORIZONS_MIN = [15, 60, 1440]
PERSISTENCE_VERSION = "persistence_v1"
SUPERVISED_VERSION = "supervised_v1"


def _utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalize a datetime to a naive UTC value (tz stripped), or None if None."""
    if dt is None:
        return None
    return dt.replace(tzinfo=None)


@dataclass
class ObservationInput:
    lot_id: str
    observed_at: datetime
    occupied_slots: int
    total_slots: int
    arrivals: int = 0
    departures: int = 0
    price: float = 0.0
    sensor_confidence: float = 1.0
    source: str = "iot"
    context: dict = field(default_factory=dict)

    def occupancy_rate(self) -> float:
        if self.total_slots <= 0:
            return 0.0
        return min(1.0, max(0.0, self.occupied_slots / self.total_slots))


@dataclass
class ForecastResult:
    horizon_minutes: int
    predicted_occupancy_rate: float
    lower: Optional[float] = None
    upper: Optional[float] = None
    model_name: str = "persistence"
    model_version: str = PERSISTENCE_VERSION
    feature_version: str = "unknown"


class TwinService:
    """Stateless service over persisted twin tables (no in-memory singleton)."""

    # A supervised model is optional. It MUST only ever have been trained on
    # real observed occupancy (enforced by separation: this class never trains).
    def __init__(self) -> None:
        self._models: dict[str, Callable[[ObservationInput, int], ForecastResult]] = {}
        self._model_versions: dict[str, str] = {}

    def register_model(
        self,
        name: str,
        version: str,
        predict_fn: Callable[[ObservationInput, int], ForecastResult],
    ) -> None:
        """Register a supervised forecasting fn. `predict_fn` returns a
        ForecastResult using REAL features. Training is out of scope here."""
        self._models[name] = predict_fn
        self._model_versions[name] = version

    # ---- Observation ingestion (real evidence only) --------------------------
    def ingest_observation(self, obs: ObservationInput) -> TwinObservation:
        o = TwinObservation(
            lot_id=obs.lot_id,
            observed_at=_utc(obs.observed_at),
            occupancy_rate=obs.occupancy_rate(),
            occupied_slots=obs.occupied_slots,
            total_slots=obs.total_slots,
            arrivals=obs.arrivals,
            departures=obs.departures,
            price=float(obs.price),
            sensor_confidence=float(obs.sensor_confidence),
            source=obs.source,
            context=json.dumps(obs.context or {}),
        )
        with get_db_cm() as db:
            db.add(o)
            db.commit()
            db.refresh(o)
            obs_id = o.id
            # Derive + persist state immediately (state estimation = now).
            self._persist_state(db, o)
        # Re-query in a fresh session so callers receive an attached,
        # detatch-safe ORM instance (no detached-instance errors).
        with get_db_cm() as db:
            o = db.query(TwinObservation).filter(
                TwinObservation.id == obs_id
            ).first()
        logger.info(
            "ingested twin observation lot=%s at=%s occ=%.3f",
            o.lot_id, o.observed_at, o.occupancy_rate,
        )
        return o

    def _persist_state(self, db, obs: TwinObservation) -> TwinState:
        congestion = min(1.0, max(0.0, obs.occupancy_rate))
        st = TwinState(
            lot_id=obs.lot_id,
            state_at=obs.observed_at,
            est_occupancy_rate=obs.occupancy_rate,
            est_available_slots=max(0, obs.total_slots - obs.occupied_slots),
            est_price=float(obs.price),
            congestion_level=congestion,
            resident_share_count=0,
            confidence=float(obs.sensor_confidence),
            source_observation_id=obs.id,
        )
        db.add(st)
        db.commit()
        return st

    # ---- Forecast generation (immutable persistence) -----------------------
    def generate_forecasts(
        self,
        lot_id: str,
        as_of: Optional[datetime] = None,
        horizons: Optional[list[int]] = None,
    ) -> list[TwinForecast]:
        """Generate + persist horizon forecasts from the latest REAL observation.

        Produces a persistence baseline always, plus any registered supervised
        models. Each row is immutable; outcomes are attached later.
        """
        horizons = horizons or FORECAST_HORIZONS_MIN
        with get_db_cm() as db:
            latest = (
                db.query(TwinObservation)
                .filter(TwinObservation.lot_id == lot_id)
                .order_by(TwinObservation.observed_at.desc())
                .first()
            )
            if latest is None:
                logger.warning("no observation to forecast for lot=%s", lot_id)
                return []
            # Anchor forecasts to the latest REAL observation time, not wall-clock.
            # This keeps forecast horizons consistent with the evidence timeline
            # (principle 2: every forecast links to its observed input timestamp).
            as_of = _utc(as_of) or latest.observed_at

            inputs = ObservationInput(
                lot_id=latest.lot_id,
                observed_at=latest.observed_at,
                occupied_slots=latest.occupied_slots,
                total_slots=latest.total_slots,
                arrivals=latest.arrivals or 0,
                departures=latest.departures or 0,
                price=latest.price or 0.0,
                sensor_confidence=latest.sensor_confidence or 1.0,
                source=latest.source,
                context=json.loads(latest.context or "{}"),
            )

            results: list[ForecastResult] = []
            # Baseline: persistence (honest, deterministic).
            results.append(self._persistence(inputs))
            # Registered supervised models (trained only on real data).
            for name, fn in self._models.items():
                try:
                    results.append(fn(inputs, 0))
                except Exception as e:  # never crash the forecast loop
                    logger.warning("model %s forecast failed: %s", name, e)

            rows: list[TwinForecast] = []
            for r in results:
                for h in horizons:
                    target = as_of + timedelta(minutes=h)
                    fc = TwinForecast(
                        lot_id=lot_id,
                        generated_at=as_of,
                        target_at=target,
                        horizon_minutes=h,
                        predicted_occupancy_rate=float(r.predicted_occupancy_rate),
                        lower_occupancy_rate=r.lower,
                        upper_occupancy_rate=r.upper,
                        model_name=r.model_name,
                        model_version=r.model_version,
                        feature_version=r.feature_version,
                        input_observation_id=latest.id,
                    )
                    db.add(fc)
                    rows.append(fc)
            db.commit()
            for r in rows:
                db.refresh(r)
            logger.info(
                "generated %d forecasts for lot=%s as_of=%s",
                len(rows), lot_id, as_of,
            )
            return rows

    @staticmethod
    def _persistence(obs: ObservationInput) -> ForecastResult:
        """Persistence baseline: occupancy does not change by default."""
        return ForecastResult(
            horizon_minutes=0,
            predicted_occupancy_rate=obs.occupancy_rate(),
            lower=max(0.0, obs.occupancy_rate() - 0.05),
            upper=min(1.0, obs.occupancy_rate() + 0.05),
            model_name="persistence",
            model_version=PERSISTENCE_VERSION,
        )

    # ---- Evaluation: match later real observations -------------------------
    def evaluate_forecasts(
        self,
        lot_id: Optional[str] = None,
        before: Optional[datetime] = None,
    ) -> int:
        """Attach real observed outcomes to forecasts and compute error.

        For each forecast with no outcome yet, find the FIRST real observation
        at/after ``target_at`` and store the actual value + signed/abs error.
        The original prediction is NEVER overwritten.
        """
        before = _utc(before)
        matched = 0
        with get_db_cm() as db:
            q = db.query(TwinForecast).filter(
                TwinForecast.actual_occupancy_rate.is_(None)
            )
            if lot_id is not None:
                q = q.filter(TwinForecast.lot_id == lot_id)
            if before is not None:
                q = q.filter(TwinForecast.generated_at < before)
            pending = q.order_by(TwinForecast.target_at.asc()).all()
            for fc in pending:
                actual = (
                    db.query(TwinObservation)
                    .filter(
                        and_(
                            TwinObservation.lot_id == fc.lot_id,
                            TwinObservation.observed_at >= fc.target_at,
                        )
                    )
                    .order_by(TwinObservation.observed_at.asc())
                    .first()
                )
                if actual is None:
                    continue
                err = round(actual.occupancy_rate - fc.predicted_occupancy_rate, 6)
                fc.actual_occupancy_rate = actual.occupancy_rate
                fc.evaluated_at = _utc(datetime.now(timezone.utc))
                fc.error = err
                fc.abs_error = abs(err)
                matched += 1
            db.commit()
        if matched:
            logger.info("evaluated %d twin forecasts", matched)
        return matched

    # ---- Scenario runs (never mutate production, principle 8) ----------
    def persist_scenario_run(
        self,
        *,
        lot_id: str,
        scenario_type: str,
        kind: str,  # 'deterministic' | 'learned' | 'calibrated'
        params: Optional[dict] = None,
        random_seed: Optional[int] = None,
        model_version: Optional[str] = None,
        predicted_occupancy_rate: Optional[float] = None,
        predicted_price: Optional[float] = None,
        lower_occupancy_rate: Optional[float] = None,
        upper_occupancy_rate: Optional[float] = None,
        assumptions: str = "",
        uncertainty_note: str = "",
        safety_note: str = "",
        base_state_ref: Optional[str] = None,
        evaluation_outcome: Optional[str] = None,
        latency_ms: Optional[float] = None,
    ) -> TwinScenarioRun:
        """Persist a scenario evaluation. It ONLY records a recommendation; it never
        writes to production occupancy / pricing / actuators (principle 8)."""
        run = TwinScenarioRun(
            lot_id=lot_id,
            created_at=_utc(datetime.now(timezone.utc)),
            scenario_type=scenario_type,
            params=json.dumps(params or {}),
            random_seed=random_seed,
            kind=kind,
            model_version=model_version,
            predicted_occupancy_rate=predicted_occupancy_rate,
            predicted_price=predicted_price,
            lower_occupancy_rate=lower_occupancy_rate,
            upper_occupancy_rate=upper_occupancy_rate,
            assumptions=assumptions,
            uncertainty_note=uncertainty_note,
            safety_note=safety_note or "Scenario is a recommendation only; it does not mutate production state or pricing.",
            base_state_ref=base_state_ref,
            evaluation_outcome=evaluation_outcome or "",
            latency_ms=latency_ms,
        )
        with get_db_cm() as db:
            db.add(run)
            db.commit()
            db.refresh(run)
        return run

    # ---- Model version provenance (principle 2) -----------------------
    def register_model_version(
        self,
        *,
        model_name: str,
        artifact_version: str,
        training_data_cutoff: Optional[datetime] = None,
        feature_schema_version: str = "unknown",
        validation_metrics: Optional[dict] = None,
        is_baseline: bool = False,
        promotion_status: str = "candidate",
    ) -> TwinModelVersion:
        """Record model provenance. `validation_metrics` must come from REAL data
        evaluation, never synthetic (principle 7)."""
        mv = TwinModelVersion(
            model_name=model_name,
            artifact_version=artifact_version,
            training_data_cutoff=_utc(training_data_cutoff),
            feature_schema_version=feature_schema_version,
            validation_metrics=json.dumps(validation_metrics or {}),
            promotion_status=promotion_status,
            is_baseline=is_baseline,
            created_at=_utc(datetime.now(timezone.utc)),
        )
        with get_db_cm() as db:
            db.add(mv)
            db.commit()
            db.refresh(mv)
        return mv

    # ---- Metrics (honest, per horizon + model) ------------------------
    # Nominal interval coverage target for the persisted [lower, upper] band.
    TARGET_COVERAGE = 0.90

    def metrics(self, lot_id: Optional[str] = None) -> list[dict]:
        """Per (model, version, horizon) forecast quality on REAL outcomes.

        Reports every metric enumerated in the plan's Required Metrics section:
        MAE/RMSE by horizon+lot, bias, interval coverage, calibration error,
        skill vs the persistence baseline, vs the best ML model, drift (recent
        vs older MAE), and the count / fraction of forecasts evaluated.
        """
        with get_db_cm() as db:
            q = db.query(TwinForecast)
            if lot_id is not None:
                q = q.filter(TwinForecast.lot_id == lot_id)
            all_fc = q.all()
        evals = [f for f in all_fc if f.actual_occupancy_rate is not None]
        total_by_key: dict[tuple, int] = {}
        for f in all_fc:
            k = (f.model_name, f.model_version, f.horizon_minutes)
            total_by_key[k] = total_by_key.get(k, 0) + 1

        # group evaluated forecasts by (model_name, model_version, horizon)
        groups: dict[tuple, list[TwinForecast]] = {}
        for fc in evals:
            key = (fc.model_name, fc.model_version, fc.horizon_minutes)
            groups.setdefault(key, []).append(fc)

        # MAE of the persistence baseline per horizon (skill-score denominator).
        persistence_mae: dict[int, float] = {}
        for (mn, _mv, h), fcs in groups.items():
            if mn == "persistence":
                ae = [f.abs_error for f in fcs if f.abs_error is not None]
                if ae:
                    persistence_mae[h] = sum(ae) / len(ae)
        # Best (lowest-MAE) non-persistence "ML" model MAE per horizon.
        ml_mae: dict[int, float] = {}
        for (mn, _mv, h), fcs in groups.items():
            if mn == "persistence":
                continue
            ae = [f.abs_error for f in fcs if f.abs_error is not None]
            if ae:
                m = sum(ae) / len(ae)
                if h not in ml_mae or m < ml_mae[h]:
                    ml_mae[h] = m

        rows = []
        for (mn, mv, h), fcs in sorted(groups.items()):
            errs = [f.error for f in fcs if f.error is not None]
            abs_errs = [f.abs_error for f in fcs if f.abs_error is not None]
            n = len(fcs)
            mae = sum(abs_errs) / n if n else 0.0
            mse = sum(e * e for e in errs) / n if n else 0.0
            bias = sum(errs) / n if n else 0.0
            # Interval coverage (share of actuals inside [lower, upper]).
            covered = 0
            have_int = 0
            for f in fcs:
                if (
                    f.lower_occupancy_rate is not None
                    and f.upper_occupancy_rate is not None
                    and f.actual_occupancy_rate is not None
                ):
                    have_int += 1
                    if f.lower_occupancy_rate <= f.actual_occupancy_rate <= f.upper_occupancy_rate:
                        covered += 1
            coverage = (covered / have_int) if have_int else None
            # Calibration error = |empirical coverage - nominal target|.
            calib_err = (
                abs(coverage - self.TARGET_COVERAGE) if coverage is not None else None
            )
            # Skill vs persistence: 1 - mae/persistence_mae (>0 = beats baseline).
            base = persistence_mae.get(h)
            skill_vs_persistence = (
                round(1.0 - (mae / base), 6) if base and base > 0 else None
            )
            mae_minus_ml = (
                round(mae - ml_mae[h], 6) if h in ml_mae else None
            )
            # Drift: recent-half MAE minus older-half MAE (time-ordered).
            drift = None
            if n >= 4:
                ordered = sorted(
                    (f for f in fcs if f.abs_error is not None),
                    key=lambda f: f.generated_at,
                )
                half = len(ordered) // 2
                older = ordered[:half]
                recent = ordered[half:]
                if older and recent:
                    om = sum(f.abs_error for f in older) / len(older)
                    rm = sum(f.abs_error for f in recent) / len(recent)
                    drift = round(rm - om, 6)
            total = total_by_key.get((mn, mv, h), n)
            rows.append(
                {
                    "lot_id": fcs[0].lot_id,
                    "model_name": mn,
                    "model_version": mv,
                    "horizon_minutes": h,
                    "n_evaluated": n,
                    "n_forecasts": total,
                    "evaluated_fraction": round(n / total, 4) if total else None,
                    "mae": round(mae, 6),
                    "rmse": round(mse ** 0.5, 6),
                    "bias": round(bias, 6),
                    "interval_coverage": round(coverage, 4) if coverage is not None else None,
                    "calibration_error": round(calib_err, 4) if calib_err is not None else None,
                    "skill_vs_persistence": skill_vs_persistence,
                    "mae_minus_best_ml": mae_minus_ml,
                    "drift_recent_minus_older_mae": drift,
                }
            )
        return rows

    # ---- Scenario backtest (Required Metric: scenario backtest error) --------
    def backtest_scenarios(self, lot_id: Optional[str] = None) -> list[dict]:
        """Backtest error by intervention type for persisted scenario runs.

        For each ``TwinScenarioRun`` that predicted an occupancy rate, find the
        FIRST real observation at/after the run's ``created_at`` and record the
        signed/abs error as the run's ``evaluation_outcome`` (never overwriting
        the original prediction). Aggregates absolute error by intervention
        (scenario_type) + determinism kind. Read-only; never actuates.
        """
        matched = 0
        by_kind: dict[tuple, list[float]] = {}
        latencies: dict[tuple, list[float]] = {}
        with get_db_cm() as db:
            q = db.query(TwinScenarioRun).filter(
                TwinScenarioRun.predicted_occupancy_rate.isnot(None)
            )
            if lot_id is not None:
                q = q.filter(TwinScenarioRun.lot_id == lot_id)
            runs = q.order_by(TwinScenarioRun.created_at.asc()).all()
            for run in runs:
                key = (run.scenario_type, run.kind)
                if run.latency_ms is not None:
                    latencies.setdefault(key, []).append(float(run.latency_ms))
                actual = (
                    db.query(TwinObservation)
                    .filter(
                        and_(
                            TwinObservation.lot_id == run.lot_id,
                            TwinObservation.observed_at >= run.created_at,
                        )
                    )
                    .order_by(TwinObservation.observed_at.asc())
                    .first()
                )
                if actual is None:
                    continue
                err = round(actual.occupancy_rate - run.predicted_occupancy_rate, 6)
                run.evaluation_outcome = json.dumps(
                    {
                        "actual_occupancy_rate": actual.occupancy_rate,
                        "error": err,
                        "abs_error": abs(err),
                        "matched_observation_at": actual.observed_at.isoformat(),
                    }
                )
                by_kind.setdefault(key, []).append(abs(err))
                matched += 1
            db.commit()
        rows = []
        keys = set(by_kind) | set(latencies)
        for (stype, kind) in sorted(keys):
            aes = by_kind.get((stype, kind), [])
            lats = latencies.get((stype, kind), [])
            rows.append(
                {
                    "scenario_type": stype,
                    "kind": kind,
                    "n_backtested": len(aes),
                    "backtest_mae": round(sum(aes) / len(aes), 6) if aes else None,
                    "mean_latency_ms": round(sum(lats) / len(lats), 3) if lats else None,
                }
            )
        if matched:
            logger.info("backtested %d twin scenario runs", matched)
        return rows


# Module-level default service (constructed per-request is fine too; this just
# avoids re-registering models on every call). NOT a singleton holding state —
# all state lives in the database.
twin_service = TwinService()
