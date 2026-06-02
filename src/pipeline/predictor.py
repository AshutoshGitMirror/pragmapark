import os
import logging
from typing import Any
import numpy as np
import pandas as pd
from src.constants import RF_WEIGHT, XGB_WEIGHT
from src.features.builder import safe_predict
from src.models.download import ensure_model

logger = logging.getLogger(__name__)
MAX_HISTORY = 100
MIN_SAMPLES = 10
MODEL_DIR: str = os.getenv("MODEL_ARTIFACT_PATH", "src/models/artifacts")


class Predictor:
    def __init__(self):
        self.rf: Any | None = None
        self.xgb: Any | None = None
        self.meta: Any | None = None
        self._loaded: bool = False

    def ensure(self) -> None:
        if not self._loaded:
            self._load()
            self._loaded = True

    def _load(self) -> None:
        self.rf = ensure_model("rf", MODEL_DIR)
        self.xgb = ensure_model("xgb", MODEL_DIR)
        self.meta = ensure_model("meta", MODEL_DIR)

    def predict(self, features: pd.Series) -> float:
        self.ensure()
        rf = self.rf
        xgb = self.xgb
        if rf is None or xgb is None:
            logger.warning("FALLBACK: models not loaded, using simple fallback")
            val = features.get("occupancy_rate")
            if val is None:
                val = features.get("occ_lag_15m")
            if val is None:
                val = 0.5
            return float(val)
        meta = self.meta

        def ensemble(X: pd.DataFrame) -> float:
            pred_rf = float(rf.predict(X)[0])
            pred_xgb = float(xgb.predict(X)[0])
            if not np.isfinite(pred_rf) or not np.isfinite(pred_xgb):
                logger.warning(f"Non-finite prediction: rf={pred_rf}, xgb={pred_xgb}")
                return 0.5
            if meta is not None:
                meta_in = np.array([[pred_rf, pred_xgb]])
                pred = float(meta.predict(meta_in)[0])
                if not np.isfinite(pred):
                    logger.warning("Non-finite meta prediction, using ensemble fallback")
                    pred = RF_WEIGHT * pred_rf + XGB_WEIGHT * pred_xgb
            else:
                pred = RF_WEIGHT * pred_rf + XGB_WEIGHT * pred_xgb
            return float(np.clip(pred, 0.0, 1.0))

        return safe_predict(ensemble, features)

    @property
    def summary(self) -> dict:
        return {"rf": self.rf is not None, "xgb": self.xgb is not None, "loaded": self._loaded}
