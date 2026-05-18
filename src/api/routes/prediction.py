import numpy as np
import pandas as pd
import joblib
import os
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/v1/predict", tags=["Prediction"])

MODEL_DIR = "src/models/artifacts"


def _load_models():
    rf_path = os.path.join(MODEL_DIR, "rf_model.joblib")
    xgb_path = os.path.join(MODEL_DIR, "xgb_model.joblib")
    if not os.path.exists(rf_path) or not os.path.exists(xgb_path):
        return None, None
    return joblib.load(rf_path), joblib.load(xgb_path)


@router.post("/occupancy")
async def predict_occupancy(
    occupied_slots: float, total_slots: float,
    occ_lag_15m: float, occ_lag_1h: float,
    net_flux: float, hour: int = 12,
):
    rf, xgb = _load_models()
    if rf is None or xgb is None:
        raise HTTPException(503, "Models not trained. Run src/models/train_real.py first.")

    hour_sin = np.sin(2 * np.pi * hour / 24)
    hour_cos = np.cos(2 * np.pi * hour / 24)

    X = pd.DataFrame([[occupied_slots, total_slots, occ_lag_15m, occ_lag_1h,
                        net_flux, hour_sin, hour_cos]],
                     columns=["occupied_slots", "total_slots", "occ_lag_15m",
                              "occ_lag_1h", "net_flux", "hour_sin", "hour_cos"])

    pred_rf = float(rf.predict(X)[0])
    pred_xgb = float(xgb.predict(X)[0])
    ensemble = 0.4 * pred_rf + 0.6 * pred_xgb

    return {
        "rf_prediction": round(pred_rf, 4),
        "xgb_prediction": round(pred_xgb, 4),
        "ensemble_prediction": round(ensemble, 4),
    }


@router.get("/health")
async def model_health():
    rf, xgb = _load_models()
    return {
        "rf_loaded": rf is not None,
        "xgb_loaded": xgb is not None,
        "status": "healthy" if (rf is not None and xgb is not None) else "unhealthy",
    }
