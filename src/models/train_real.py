import pandas as pd
import numpy as np
import os
import sys
import joblib
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error

# Ensure project root is in path
sys.path.append(os.getcwd())

def train_chronological_ensemble(features):
    """
    Phase 2: Birmingham Chronological Validation.
    """
    # Sort by time
    features = features.sort_values('ts_bucket')
    
    # ── Feature Augmentation ───────────
    features['hour'] = features['ts_bucket'].dt.hour
    features['hour_sin'] = np.sin(2 * np.pi * features['hour'] / 24)
    features['hour_cos'] = np.cos(2 * np.pi * features['hour'] / 24)
    
    X_cols = [
        'occupied_slots', 'total_slots', 'occ_lag_15m', 'occ_lag_1h', 
        'net_flux', 'hour_sin', 'hour_cos'
    ]
    X = features[X_cols]
    y = features['target']
    
    # Chronological Split
    split_idx = int(len(features) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    # Model Tuning
    rf = RandomForestRegressor(n_estimators=100, max_depth=8, random_state=42, n_jobs=-1)
    xgb = XGBRegressor(n_estimators=200, max_depth=6, learning_rate=0.05, random_state=42)

    rf.fit(X_train, y_train)
    xgb.fit(X_train, y_train)

    # Ensemble
    rf_preds = rf.predict(X_test)
    xgb_preds = xgb.predict(X_test)
    ensemble_preds = (0.4 * rf_preds) + (0.6 * xgb_preds)

    mae = mean_absolute_error(y_test, ensemble_preds)
    print(f"\n[Gemini Birmingham Validation] Chronological MAE: {mae:.5f}")
    
    # Persist Artifacts
    os.makedirs("src/models/artifacts", exist_ok=True)
    joblib.dump(rf, "src/models/artifacts/rf_model.joblib")
    joblib.dump(xgb, "src/models/artifacts/xgb_model.joblib")
    
    if mae < 0.10:
        print("RESULT: VERIFIED. High-fidelity temporal forecasting achieved on real data.")
    
    return mae

if __name__ == "__main__":
    from src.features.engine import process_raw_to_features
    # FIX: Point to Birmingham dataset
    RAW_PATH = "data/raw/birmingham_parking.csv"
    features = process_raw_to_features(RAW_PATH)
    train_chronological_ensemble(features)
