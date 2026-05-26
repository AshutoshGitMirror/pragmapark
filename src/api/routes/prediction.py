import numpy as np
import pandas as pd
import joblib
import os
from fastapi import APIRouter, HTTPException, Depends
from src.api.auth import get_current_user
from src.constants import RF_WEIGHT, XGB_WEIGHT, EXPECTED_FEATURE_COLS
from src.api.schemas import PredictionRequest, PredictionResponse, ModelHealthResponse

router = APIRouter(prefix="/api/v1/predict", tags=["Prediction"])

MODEL_DIR = os.getenv("PREDICTION_MODEL_DIR", "src/models/artifacts")

X_COLS = EXPECTED_FEATURE_COLS


def _load_models():
    rf_path = os.path.join(MODEL_DIR, "rf_model.joblib")
    xgb_path = os.path.join(MODEL_DIR, "xgb_model.joblib")
    if not os.path.exists(rf_path) or not os.path.exists(xgb_path):
        return None, None
    try:
        return joblib.load(rf_path), joblib.load(xgb_path)
    except Exception:
        return None, None


def _build_feature_row(occupied_slots: float, total_slots: float,
                       occ_lag_15m: float, occ_lag_1h: float,
                       net_flux: float, hour: int) -> pd.DataFrame:
    data = {
        "occupied_slots": occupied_slots, "total_slots": total_slots,
        "occ_lag_15m": occ_lag_15m, "occ_lag_1h": occ_lag_1h, "net_flux": net_flux,
        "pe_arrival_rate": 0.0, "pe_departure_rate": 0.0,
        "pe_turnover": 0.0, "pe_anomaly": 0.0, "pe_change_point": 0.0,
        "hour_sin": np.sin(2 * np.pi * hour / 24),
        "hour_cos": np.cos(2 * np.pi * hour / 24),
        "hour_sq": (hour - 12) / 12,
        "dow_sin": 0.0, "dow_cos": 0.0, "is_weekend": 0.0,
        "occ_roll_mean_3h": 0.0, "occ_roll_std_3h": 0.0, "occ_acceleration": 0.0,
    }
    return pd.DataFrame([data], columns=X_COLS)


@router.post("/occupancy", response_model=PredictionResponse)
async def predict_occupancy(
    body: PredictionRequest,
    user=Depends(get_current_user),
):
    rf, xgb = _load_models()
    if rf is None or xgb is None:
        raise HTTPException(503, "Models not trained. Run src/models/train_real.py first.")

    X = _build_feature_row(body.occupied_slots, body.total_slots, body.occ_lag_15m, body.occ_lag_1h, body.net_flux, body.hour)

    pred_rf = float(rf.predict(X)[0])
    pred_xgb = float(xgb.predict(X)[0])
    ensemble = RF_WEIGHT * pred_rf + XGB_WEIGHT * pred_xgb

    return PredictionResponse(
        rf_prediction=round(pred_rf, 4),
        xgb_prediction=round(pred_xgb, 4),
        ensemble_prediction=round(ensemble, 4),
    )


@router.get("/health", response_model=ModelHealthResponse)
async def model_health(user: dict = Depends(get_current_user)):
    rf, xgb = _load_models()
    return ModelHealthResponse(
        rf_loaded=rf is not None,
        xgb_loaded=xgb is not None,
        status="healthy" if (rf is not None and xgb is not None) else "unhealthy",
    )
