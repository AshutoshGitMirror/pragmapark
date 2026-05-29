import pandas as pd
import numpy as np
import joblib
import os
import tempfile
from src.pipeline.predictor import Predictor


class _DummyModel:
    def __init__(self, val=0.7):
        self.val = val
    def predict(self, X):
        return np.array([self.val])


class TestPredictor:
    def test_summary_initial(self):
        p = Predictor()
        s = p.summary
        assert s["rf"] is False
        assert s["xgb"] is False
        assert s["loaded"] is False

    def test_ensure_does_not_crash(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmpdir:
            monkeypatch.setattr("src.pipeline.predictor.MODEL_DIR", tmpdir)
            monkeypatch.setenv("PRAGMA_ENV", "testing")
            p = Predictor()
            p.ensure()
            assert p._loaded is True
            assert p.rf is None
            assert p.xgb is None

    def test_predict_fallback_when_no_models(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmpdir:
            monkeypatch.setattr("src.pipeline.predictor.MODEL_DIR", tmpdir)
            monkeypatch.setenv("PRAGMA_ENV", "testing")
            p = Predictor()
            features = pd.Series({"occupancy_rate": 0.6, "occ_lag_15m": 0.5})
            result = p.predict(features)
            assert result == 0.6

    def test_predict_fallback_to_lag_when_no_occ_rate(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmpdir:
            monkeypatch.setattr("src.pipeline.predictor.MODEL_DIR", tmpdir)
            monkeypatch.setenv("PRAGMA_ENV", "testing")
            p = Predictor()
            features = pd.Series({"occ_lag_15m": 0.42})
            result = p.predict(features)
            assert result == 0.42

    def test_predict_uses_loaded_model(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmpdir:
            rf_path = os.path.join(tmpdir, "rf_model.joblib")
            xgb_path = os.path.join(tmpdir, "xgb_model.joblib")
            joblib.dump(_DummyModel(0.7), rf_path)
            joblib.dump(_DummyModel(0.7), xgb_path)
            monkeypatch.setattr("src.pipeline.predictor.MODEL_DIR", tmpdir)
            p = Predictor()
            features = pd.Series({"occupancy_rate": 0.5, "occ_lag_15m": 0.4})
            result = p.predict(features)
            assert 0.0 <= result <= 1.0
            assert p.rf is not None
            assert p.xgb is not None

    def test_summary_after_load(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmpdir:
            rf_path = os.path.join(tmpdir, "rf_model.joblib")
            xgb_path = os.path.join(tmpdir, "xgb_model.joblib")
            joblib.dump(_DummyModel(0.5), rf_path)
            joblib.dump(_DummyModel(0.5), xgb_path)
            monkeypatch.setattr("src.pipeline.predictor.MODEL_DIR", tmpdir)
            p = Predictor()
            p.ensure()
            s = p.summary
            assert s["rf"] is True
            assert s["xgb"] is True
            assert s["loaded"] is True
