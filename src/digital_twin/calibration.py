"""Calibrated scenario uncertainty — the honest replacement for the old
generative CVAE-WGAN counterfactual component (plan P5).

WHY THIS EXISTS (instead of only deleting the generator)
---------------------------------------------------------
P5 of the remediation plan says: "Remove or rebuild CVAE-WGAN (recommended:
remove from runtime, deterministic engine + **calibrated quantile/bootstrap**;
offline-only; versioned artifact)." The deterministic engine already lives in
``scenario.py``. This module supplies the *calibrated quantile/bootstrap* half:
a real, versioned, uncertainty-estimation component built **only from observed
data**. It is the best-form re-implementation of the removed generative part —
and unlike the removed part it is scientifically defensible:

  * It never invents values. The intervals are EMPIRICAL quantiles of real
    observed occupancy transition residuals, or bootstrap replicates drawn
    from real observations. No synthetic sample is ever used as evidence.
  * It is clearly labelled ``kind="calibrated"`` (never ``learned``) because
    it does not fit an intervention->outcome model and does not claim causal
    structure (principle 4).
  * It is OFFLINE-ONLY: it is not imported by the runtime forecasting path and
    never trains or feeds a production model (principle 1).
  * It never mutates production (principle 8): every output is persisted as a
    read-only ``TwinScenarioRun`` recommendation.

The component wraps a deterministic scenario from ``scenario.py`` and attaches
an honest uncertainty band derived from real data, then persists the result as
a versioned, calibrated run.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

import numpy as np
import time

from src.api.database import get_db_cm
from src.digital_twin.orm import TwinObservation, TwinScenarioRun
from src.digital_twin.scenario import ScenarioEngine
from src.digital_twin.service import TwinService, _utc

logger = logging.getLogger(__name__)

CALIBRATION_VERSION = "calibration_v1"


@dataclass
class CalibrationFit:
    """Empirical uncertainty model fitted on REAL observed occupancy changes.

    NOT a generative model. It simply records the distribution of observed
    occupancy deltas over a fixed horizon, so we can produce honest quantile
    intervals. ``n`` is the number of real observations behind the fit — when
    it is too small the band is flagged as low-confidence and the run is
    explicitly labelled experimental (principle 7: sparse data is not evidence).
    """

    horizon_minutes: int
    lower_q: float
    upper_q: float
    mean_delta: float
    std_delta: float
    n: int
    low_confidence: bool = False

    def interval(self, center: float) -> tuple[float, float]:
        lo = float(np.clip(center + self.lower_q, 0.0, 1.0))
        hi = float(np.clip(center + self.upper_q, 0.0, 1.0))
        # Guarantee a non-degenerate, ordered interval.
        if hi < lo:
            hi = min(1.0, lo + 1e-6)
        return lo, hi

    def to_dict(self) -> dict:
        return {
            "horizon_minutes": self.horizon_minutes,
            "lower_q": self.lower_q,
            "upper_q": self.upper_q,
            "mean_delta": self.mean_delta,
            "std_delta": self.std_delta,
            "n": self.n,
            "low_confidence": self.low_confidence,
        }


def _observed_occupancy_deltas(
    lot_id: str, horizon_minutes: int, db=None
) -> List[float]:
    """Return REAL occupancy changes between observations roughly ``horizon`` apart.

    Uses the persisted ``TwinObservation`` table only — never simulated values
    (principle 1). Pairs are formed by stepping through time-ordered
    observations and matching each to the next observation whose timestamp is at
    least ``horizon_minutes`` later. If ``db`` (an active session) is passed it is
    reused; otherwise a new session is opened via ``get_db_cm`` and closed here.
    """
    from src.api.database import get_db_cm

    if db is not None:
        return _observed_occupancy_deltas_with(lot_id, horizon_minutes, db)
    with get_db_cm() as db:
        return _observed_occupancy_deltas_with(lot_id, horizon_minutes, db)


def _observed_occupancy_deltas_with(
    lot_id: str, horizon_minutes: int, db
) -> List[float]:
    rows = (
        db.query(
            TwinObservation.observed_at,
            TwinObservation.occupancy_rate,
        )
        .filter(TwinObservation.lot_id == lot_id)
        .order_by(TwinObservation.observed_at.asc())
        .all()
    )
    if len(rows) < 2:
        return []
    deltas: List[float] = []
    i = 0
    while i < len(rows) - 1:
        t0, o0 = rows[i]
        target = t0 + _timedelta_minutes(horizon_minutes)
        j = i + 1
        while j < len(rows) and rows[j][0] < target:
            j += 1
        if j < len(rows):
            t1, o1 = rows[j]
            # Only keep pairs that are genuinely ~horizon apart (not huge gaps).
            gap_min = (t1 - t0).total_seconds() / 60.0
            if gap_min <= horizon_minutes * 3:
                deltas.append(o1 - o0)
            i = j
        else:
            break
    return deltas


def _timedelta_minutes(minutes: int) -> object:
    from datetime import timedelta

    return timedelta(minutes=minutes)


def fit_calibration(
    lot_id: str,
    horizon_minutes: int = 60,
    lower: float = 0.05,
    upper: float = 0.95,
    min_samples: int = 20,
    db=None,
) -> CalibrationFit:
    """Fit an empirical quantile band from REAL observed occupancy deltas.

    This is the calibrated replacement for the removed generative component:
    instead of sampling a (unvalidated) CVAE-WGAN, we report where real
    occupancy *actually* moved over the same horizon.
    """
    deltas = _observed_occupancy_deltas(lot_id, horizon_minutes, db=db)
    n = len(deltas)
    if n < 2:
        # No real evidence: return a wide, explicitly low-confidence band.
        return CalibrationFit(
            horizon_minutes=horizon_minutes,
            lower_q=-0.5,
            upper_q=0.5,
            mean_delta=0.0,
            std_delta=0.5,
            n=n,
            low_confidence=True,
        )
    arr = np.array(deltas, dtype=float)
    lq = float(np.quantile(arr, lower))
    uq = float(np.quantile(arr, upper))
    return CalibrationFit(
        horizon_minutes=horizon_minutes,
        lower_q=lq,
        upper_q=uq,
        mean_delta=float(np.mean(arr)),
        std_delta=float(np.std(arr)),
        n=n,
        low_confidence=n < min_samples,
    )


def bootstrap_band(
    lot_id: str,
    center: float,
    horizon_minutes: int = 60,
    n_boot: int = 200,
    alpha: float = 0.05,
    seed: Optional[int] = None,
    db=None,
) -> tuple[float, float, int]:
    """Bootstrap a percentile interval for a scenario outcome using REAL deltas.

    We resample (with replacement) the real observed occupancy deltas and add
    them to ``center`` to get a non-parametric prediction interval. This is the
    honest, data-driven analogue of the removed stochastic generator: it
    quantifies uncertainty from observed variance, never from a fitted
    generative network. Returns (lower, upper, n_real_samples).
    """
    deltas = _observed_occupancy_deltas(lot_id, horizon_minutes, db=db)
    if len(deltas) < 2:
        # No real evidence: degenerate wide band, flagged via n=0 caller-side.
        return (0.0, 1.0, 0)
    rng = np.random.default_rng(seed)
    arr = np.array(deltas, dtype=float)
    boot = rng.choice(arr, size=(n_boot, len(arr)), replace=True)
    shifted = center + boot.mean(axis=1)
    shifted = np.clip(shifted, 0.0, 1.0)
    lo = float(np.quantile(shifted, alpha / 2))
    hi = float(np.quantile(shifted, 1 - alpha / 2))
    if hi < lo:
        hi = min(1.0, lo + 1e-6)
    return (lo, hi, len(deltas))


@dataclass
class CalibratedScenarioResult:
    scenario: str
    kind: str = "calibrated"
    predicted_occupancy_rate: Optional[float] = None
    predicted_price: Optional[float] = None
    lower_occupancy_rate: Optional[float] = None
    upper_occupancy_rate: Optional[float] = None
    assumptions: List[str] = field(default_factory=list)
    uncertainty_note: str = ""
    safety_note: str = (
        "Projection only. Does NOT mutate production state or pricing; an "
        "operator or the RL controller must decide before any action is taken."
    )
    base_state_ref: Optional[str] = None
    experimental: bool = False
    n_real_samples: int = 0


class CalibratedScenarioRunner:
    """Offline, versioned wrapper that turns a deterministic scenario into a
    calibrated, uncertainty-bounded run persisted as ``TwinScenarioRun``.

    KEY PROPERTIES
    --------------
    * Purely offline: instantiated on demand, holds no production state.
    * Uses only real observed deltas (``fit_calibration`` / ``bootstrap_band``).
    * Persists results through ``TwinService.persist_scenario_run`` so every
      run is durable and auditable (principle 3 separation of simulation vs
      production control).
    * Never auto-actuates (principle 8).
    """

    def __init__(self, service: Optional[TwinService] = None):
        self.service = service or TwinService()
        self.engine = ScenarioEngine()
        self.engine.register_defaults()
        self._version_registered: set = set()

    def _ensure_version(self, fit: CalibrationFit) -> str:
        version = f"{CALIBRATION_VERSION}_h{fit.horizon_minutes}"
        if version not in self._version_registered:
            self.service.register_model_version(
                model_name="twin_calibration",
                artifact_version=version,
                feature_schema_version="observed_delta_v1",
                validation_metrics={
                    "n_real_samples": fit.n,
                    "mean_delta": fit.mean_delta,
                    "std_delta": fit.std_delta,
                    "low_confidence": fit.low_confidence,
                },
                is_baseline=True,
                promotion_status="calibrated_offline",
            )
            self._version_registered.add(version)
        return version

    def run_scenario(
        self,
        lot_id: str,
        scenario_name: str,
        base_state: dict,
        horizon_minutes: int = 60,
        use_bootstrap: bool = True,
        seed: Optional[int] = None,
    ) -> CalibratedScenarioResult:
        """Run one deterministic scenario and attach a real-data uncertainty band.

        The scenario projection (deterministic, from ``scenario.py``) is the
        point estimate; the band comes from real observed occupancy deltas over
        the same horizon. Persisted as a ``calibrated`` ``TwinScenarioRun``.
        """
        scenario = next(
            (s for s in self.engine.scenarios if s.name == scenario_name), None
        )
        if scenario is None:
            raise ValueError(f"unknown scenario: {scenario_name}")

        # Measure scenario latency (plan Required Metric: "scenario latency").
        t0 = time.perf_counter()
        modified = scenario.run(base_state)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        center_occ = float(modified.get("occupancy_rate", base_state.get("occupancy_rate", 0.0)))
        center_price = modified.get("price", base_state.get("price"))

        fit = fit_calibration(lot_id, horizon_minutes)
        self._ensure_version(fit)

        if use_bootstrap:
            lo, hi, n_real = bootstrap_band(
                lot_id, center_occ, horizon_minutes, seed=seed
            )
        else:
            lo, hi = fit.interval(center_occ)
            n_real = fit.n

        experimental = n_real < 20 or fit.low_confidence
        uncertainty_note = (
            f"Calibrated band from {n_real} REAL observed occupancy deltas "
            f"over ~{horizon_minutes}m (empirical "
            f"q05/q95 = {fit.lower_q:+.3f}/{fit.upper_q:+.3f}). "
            f"{'LOW CONFIDENCE: insufficient real samples; band is illustrative only.' if experimental else 'Band reflects observed variance, not a causal effect.'}"
        )

        result = CalibratedScenarioResult(
            scenario=scenario_name,
            kind="calibrated",
            predicted_occupancy_rate=center_occ,
            predicted_price=center_price,
            lower_occupancy_rate=lo,
            upper_occupancy_rate=hi,
            assumptions=list(scenario.assumptions),
            uncertainty_note=uncertainty_note,
            base_state_ref=base_state.get("ref"),
            experimental=experimental,
            n_real_samples=n_real,
        )

        self.service.persist_scenario_run(
            lot_id=lot_id,
            scenario_type=scenario_name,
            kind="calibrated",
            params={
                "base_state": {k: v for k, v in base_state.items() if k != "ref"},
                "horizon_minutes": horizon_minutes,
                "use_bootstrap": use_bootstrap,
                "experimental": experimental,
            },
            random_seed=seed,
            model_version=f"{CALIBRATION_VERSION}_h{horizon_minutes}",
            predicted_occupancy_rate=center_occ,
            predicted_price=center_price,
            lower_occupancy_rate=lo,
            upper_occupancy_rate=hi,
            assumptions="; ".join(scenario.assumptions),
            uncertainty_note=uncertainty_note,
            safety_note=result.safety_note,
            base_state_ref=base_state.get("ref"),
            latency_ms=latency_ms,
        )
        logger.info(
            "calibrated scenario lot=%s scenario=%s n_real=%d experimental=%s",
            lot_id, scenario_name, n_real, experimental,
        )
        return result

    def run_all(
        self,
        lot_id: str,
        base_state: dict,
        horizon_minutes: int = 60,
        seed: Optional[int] = None,
    ) -> List[CalibratedScenarioResult]:
        results = []
        for scenario in self.engine.scenarios:
            results.append(
                self.run_scenario(
                    lot_id, scenario.name, base_state, horizon_minutes, seed=seed
                )
            )
        return results
