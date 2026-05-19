from fastapi import APIRouter, Depends
from datetime import datetime, timezone
from pydantic import BaseModel

from src.api.database import get_session, PredictionMetric
from src.api.routes.sessions import _driver_id

router = APIRouter()

class PredictRequest(BaseModel):
    lot_id: str
    driver_id: str
    occupied_slots: float = 0.0
    total_slots: int = 500
    occ_lag_15m: float = 0.0
    occ_lag_1h: float = 0.0

@router.post("/predict")
def predict_occupancy(req: PredictRequest, db=Depends(get_session)):
    from src.features.builder import build_features_from_records, safe_predict, X_COLS
    features = build_features_from_records([req], X_COLS)
    if features is None:
        pred = 0.5
    else:
        from src.pipeline.orchestrator import pipeline
        pred = pipeline._predict_occupancy(features)
    metric = PredictionMetric(
        lot_id=req.lot_id, driver_id=_driver_id(req.driver_id),
        predicted_occupancy=pred, model_version="rf+xgb+ridge",
    )
    db.add(metric)
    db.commit()
    return {"lot_id": req.lot_id, "predicted_occupancy": round(pred, 3)}
