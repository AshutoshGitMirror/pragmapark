"""Observation-driven digital twin API (P1).

Distinct from the legacy ``/digital-twin`` simulator router. Every endpoint here
operates only on persisted, real observations/forecasts. No simulator call trains
or feeds a forecast target.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.database import get_db_cm
from src.api.schemas.twin import (
    CalibratedScenarioOut,
    EvaluateRequest,
    ForecastGenerateRequest,
    ForecastOut,
    MetricRow,
    ObservationCreate,
    ObservationOut,
    ScenarioRequest,
    StateOut,
)
from src.digital_twin.calibration import CalibratedScenarioRunner
from src.digital_twin.orm import TwinForecast, TwinObservation, TwinState
from src.digital_twin.service import ObservationInput, twin_service

router = APIRouter(prefix="/api/v1/twin", tags=["twin"])


def _require_lot(db: Session, lot_id: str):
    from src.api.database import ParkingLot

    lot = db.query(ParkingLot).filter(ParkingLot.lot_id == lot_id).first()
    if lot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="lot not found"
        )


@router.post("/observations", response_model=ObservationOut, status_code=201)
def create_observation(payload: ObservationCreate):
    with get_db_cm() as db:
        _require_lot(db, payload.lot_id)
    obs = twin_service.ingest_observation(
        ObservationInput(
            lot_id=payload.lot_id,
            observed_at=payload.observed_at,
            occupied_slots=payload.occupied_slots,
            total_slots=payload.total_slots,
            arrivals=payload.arrivals,
            departures=payload.departures,
            price=payload.price,
            sensor_confidence=payload.sensor_confidence,
            source=payload.source,
            context=payload.context,
        )
    )
    return obs


@router.get("/observations/{lot_id}", response_model=list[ObservationOut])
def list_observations(lot_id: str, limit: int = 100):
    with get_db_cm() as db:
        rows = (
            db.query(TwinObservation)
            .filter(TwinObservation.lot_id == lot_id)
            .order_by(TwinObservation.observed_at.desc())
            .limit(limit)
            .all()
        )
        return rows


@router.get("/state/{lot_id}", response_model=list[StateOut])
def list_states(lot_id: str, limit: int = 10):
    with get_db_cm() as db:
        return (
            db.query(TwinState)
            .filter(TwinState.lot_id == lot_id)
            .order_by(TwinState.state_at.desc())
            .limit(limit)
            .all()
        )


@router.post("/forecasts/generate", response_model=list[ForecastOut])
def generate_forecasts(payload: ForecastGenerateRequest):
    rows = twin_service.generate_forecasts(
        lot_id=payload.lot_id,
        as_of=payload.as_of,
        horizons=payload.horizons,
    )
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no observations to forecast from",
        )
    return rows


@router.post("/forecasts/evaluate", status_code=200)
def evaluate_forecasts(payload: EvaluateRequest):
    matched = twin_service.evaluate_forecasts(lot_id=payload.lot_id)
    return {"matched": matched}


@router.get("/forecasts/{lot_id}", response_model=list[ForecastOut])
def list_forecasts(lot_id: str, limit: int = 200):
    with get_db_cm() as db:
        return (
            db.query(TwinForecast)
            .filter(TwinForecast.lot_id == lot_id)
            .order_by(TwinForecast.target_at.asc())
            .limit(limit)
            .all()
        )


@router.get("/metrics", response_model=list[MetricRow])
def metrics(lot_id: str | None = None):
    return twin_service.metrics(lot_id=lot_id)


@router.post(
    "/scenarios/calibrated",
    response_model=CalibratedScenarioOut,
    status_code=200,
)
def calibrated_scenario(payload: ScenarioRequest):
    """Run one deterministic scenario with a REAL-data calibrated uncertainty band.

    This is the honest, versioned replacement for the removed CVAE-WGAN
    generative counterfactual (plan P5). The band is empirical (quantile /
    bootstrap) over real observed occupancy deltas — never synthetic, never
    'learned' without intervention/outcome data. The result is persisted as a
    ``calibrated`` ``TwinScenarioRun`` and is a recommendation only; it never
    mutates production (principle 8).
    """
    runner = CalibratedScenarioRunner()
    try:
        result = runner.run_scenario(
            lot_id=payload.lot_id,
            scenario_name=payload.scenario,
            base_state=payload.base_state,
            horizon_minutes=payload.horizon_minutes,
            use_bootstrap=payload.use_bootstrap,
            seed=payload.seed,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        )
    return CalibratedScenarioOut(
        scenario=result.scenario,
        kind=result.kind,
        predicted_occupancy_rate=result.predicted_occupancy_rate,
        predicted_price=result.predicted_price,
        lower_occupancy_rate=result.lower_occupancy_rate,
        upper_occupancy_rate=result.upper_occupancy_rate,
        assumptions=result.assumptions,
        uncertainty_note=result.uncertainty_note,
        safety_note=result.safety_note,
        experimental=result.experimental,
        n_real_samples=result.n_real_samples,
    )
