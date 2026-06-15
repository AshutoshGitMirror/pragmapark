import numpy as np
import pandas as pd
import os
from fastapi import APIRouter, HTTPException
from src.constants import RF_WEIGHT, XGB_WEIGHT, EXPECTED_FEATURE_COLS
from src.api.schemas import (
    PredictionRequest,
    PredictionResponse,
    ModelHealthResponse,
)
from src.models.download import ensure_model

router = APIRouter(prefix="/api/v1/predict", tags=["Prediction"])

MODEL_DIR = os.getenv("PREDICTION_MODEL_DIR", "src/models/artifacts")

X_COLS = EXPECTED_FEATURE_COLS


def _load_models():
    rf = ensure_model("rf", MODEL_DIR)
    xgb = ensure_model("xgb", MODEL_DIR)
    meta = ensure_model("meta", MODEL_DIR)
    return rf, xgb, meta


def _build_feature_row(
    occupied_slots: float,
    total_slots: float,
    occ_lag_15m: float,
    occ_lag_1h: float,
    net_flux: float,
    hour: int,
    dow: int = 0,
) -> pd.DataFrame:
    """Build a full 19-feature row from available inputs.

    Computes all cyclical time features from hour/dow.
    Uses smart approximations for PE features and rolling stats:
      - occ_roll_mean_3h ≈ decayed average of lags
        (weighted toward occ_lag_15m)
      - pe_arrival_rate ≈ max(0, net_flux) spread over 4 periods
      - pe_departure_rate ≈ max(0, -net_flux) spread over 4 periods
      - pe_turnover ≈ absolute net_flux
    """
    occ_rate = occupied_slots / total_slots if total_slots > 0 else 0.0

    # Cyclical time features — computed exactly
    hour_sin = np.sin(2 * np.pi * hour / 24)
    hour_cos = np.cos(2 * np.pi * hour / 24)
    hour_sq = (hour - 12) ** 2 / 144
    dow_sin = np.sin(2 * np.pi * dow / 7)
    dow_cos = np.cos(2 * np.pi * dow / 7)
    is_weekend = 1.0 if dow >= 5 else 0.0

    # PE features — smart approximations from available data
    net_abs = abs(net_flux)
    pe_arrival = max(0.0, net_flux) / 4.0  # spread over ~1h window
    pe_departure = max(0.0, -net_flux) / 4.0
    pe_turnover = net_abs  # total churn ≈ absolute flux
    # Anomaly: compare current occ vs rolling mean of available lags
    rolling_mean = (occ_lag_15m + occ_lag_1h) / 2.0
    rolling_std = (
        abs(occ_lag_15m - occ_lag_1h) / 2.0
        if occ_lag_15m != occ_lag_1h
        else 0.05
    )
    pe_anomaly = (
        1.0
        if rolling_std > 0 and abs(occ_rate - rolling_mean) > 2.0 * rolling_std
        else 0.0
    )
    pe_change_point = (
        1.0 if net_abs > 0.15 and abs(occ_rate - rolling_mean) > 0.10 else 0.0
    )

    # Rolling stats — decay-weighted from lags
    occ_roll_mean_3h = 0.6 * occ_lag_15m + 0.3 * occ_lag_1h + 0.1 * occ_rate
    occ_roll_std_3h = (
        abs(occ_lag_15m - occ_lag_1h) * 0.5 + 0.02
    )  # minimum floor
    occ_acceleration = (
        net_flux - (occ_lag_15m - occ_lag_1h) * 4.0
    )  # second difference approx

    data = {
        "occupied_slots": occupied_slots,
        "total_slots": total_slots,
        "occ_lag_15m": occ_lag_15m,
        "occ_lag_1h": occ_lag_1h,
        "pe_net_flux": net_flux,
        "pe_arrival_rate": round(pe_arrival, 4),
        "pe_departure_rate": round(pe_departure, 4),
        "pe_turnover": round(pe_turnover, 4),
        "pe_anomaly": pe_anomaly,
        "pe_change_point": pe_change_point,
        "hour_sin": hour_sin,
        "hour_cos": hour_cos,
        "hour_sq": hour_sq,
        "dow_sin": dow_sin,
        "dow_cos": dow_cos,
        "is_weekend": is_weekend,
        "occ_roll_mean_3h": round(occ_roll_mean_3h, 4),
        "occ_roll_std_3h": round(occ_roll_std_3h, 4),
        "occ_acceleration": round(occ_acceleration, 4),
    }
    return pd.DataFrame([data], columns=pd.Index(X_COLS))


@router.post("/occupancy", response_model=PredictionResponse)
async def predict_occupancy(
    body: PredictionRequest,
):
    rf, xgb, meta = _load_models()
    if rf is None or xgb is None:
        raise HTTPException(
            503, "Models not trained. Run src/models/train_real.py first."
        )

    X = _build_feature_row(
        body.occupied_slots,
        body.total_slots,
        body.occ_lag_15m,
        body.occ_lag_1h,
        body.net_flux,
        body.hour,
        body.dow,
    )

    pred_rf = float(rf.predict(X)[0])
    pred_xgb = float(xgb.predict(X)[0])

    # Use meta-learner (RidgeCV) when available, fall back to static weights
    if meta is not None:
        meta_in = np.array([[pred_rf, pred_xgb]])
        ensemble = float(meta.predict(meta_in)[0])
        if not np.isfinite(ensemble):
            ensemble = RF_WEIGHT * pred_rf + XGB_WEIGHT * pred_xgb
    else:
        ensemble = RF_WEIGHT * pred_rf + XGB_WEIGHT * pred_xgb

    ensemble = float(np.clip(ensemble, 0.0, 1.0))

    return PredictionResponse(
        rf_prediction=round(pred_rf, 4),
        xgb_prediction=round(pred_xgb, 4),
        ensemble_prediction=round(ensemble, 4),
    )


@router.get("/health", response_model=ModelHealthResponse)
async def model_health():
    rf, xgb, meta = _load_models()
    return ModelHealthResponse(
        rf_loaded=rf is not None,
        xgb_loaded=xgb is not None,
        status="healthy"
        if (rf is not None and xgb is not None)
        else "unhealthy",
    )
