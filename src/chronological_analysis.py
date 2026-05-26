import pandas as pd
import numpy as np
import joblib
import os
import sys
import random

# Ensure project root is in path
sys.path.append(os.getcwd())

from src.constants import RF_WEIGHT, XGB_WEIGHT
from src.features.engine import process_raw_to_features

SEED = 42

def set_seeds(s: int = SEED):
    random.seed(s)
    np.random.seed(s)

def run_chronological_analysis():
    set_seeds()
    print("\n" + "="*60)
    print("CHRONOLOGICAL HOLDOUT ANALYSIS: RF vs XGB vs ENSEMBLE")
    print("="*60)

    # 1. Load Data
    RAW_PATH = "data/raw/birmingham_parking.csv"
    features = process_raw_to_features(RAW_PATH)
    features = features.sort_values('ts_bucket')
    
    # Feature Augmentation
    features['hour'] = features['ts_bucket'].dt.hour
    features['hour_sin'] = np.sin(2 * np.pi * features['hour'] / 24)
    features['hour_cos'] = np.cos(2 * np.pi * features['hour'] / 24)
    
    X_cols = [
        'occupied_slots', 'total_slots', 'occ_lag_15m', 'occ_lag_1h', 
        'net_flux', 'hour_sin', 'hour_cos'
    ]
    
    # 2. Chronological Split (80% Train, 20% Test)
    split_idx = int(len(features) * 0.8)
    test_set = features.iloc[split_idx:].copy()
    
    # 3. Load Models
    try:
        rf = joblib.load("src/models/artifacts/rf_model.joblib")
        xgb = joblib.load("src/models/artifacts/xgb_model.joblib")
    except Exception as e:
        print(f"Failed to load models: {e}")
        return
    
    # 4. Generate Detailed Predictions
    X_test = test_set[X_cols]
    test_set['rf_pred'] = rf.predict(X_test)
    test_set['xgb_pred'] = xgb.predict(X_test)
    test_set['ensemble_pred'] = (RF_WEIGHT * test_set['rf_pred']) + (XGB_WEIGHT * test_set['xgb_pred'])
    
    # 5. Output Comparison for a specific time window (Temporal Slice)
    print(f"\n[Test Context] Validating on unseen future data: {test_set['ts_bucket'].min()} to {test_set['ts_bucket'].max()}")
    print("\n" + "-"*85)
    print(f"{'Timestamp':<20} | {'Actual':<8} | {'RF Pred':<8} | {'XGB Pred':<8} | {'Ensemble':<8} | {'Error':<8}")
    print("-"*85)
    
    # Show a representative slice
    sample_slice = test_set.iloc[100:115]
    for _, row in sample_slice.iterrows():
        err = abs(row['target'] - row['ensemble_pred'])
        print(f"{str(row['ts_bucket']):<20} | {row['target']:<8.4f} | {row['rf_pred']:<8.4f} | {row['xgb_pred']:<8.4f} | {row['ensemble_pred']:<8.4f} | {err:<8.4f}")
    
    print("-"*85)
    
    # Overall Performance
    rf_mae = np.mean(np.abs(test_set['target'] - test_set['rf_pred']))
    xgb_mae = np.mean(np.abs(test_set['target'] - test_set['xgb_pred']))
    ens_mae = np.mean(np.abs(test_set['target'] - test_set['ensemble_pred']))
    
    print(f"\nOverall Test Set Performance (MAE):")
    print(f"  Random Forest: {rf_mae:.5f}")
    print(f"  XGBoost:       {xgb_mae:.5f}")
    print(f"  Hybrid Ensemble: {ens_mae:.5f}")
    
    if ens_mae < min(rf_mae, xgb_mae):
        print("\nRESULT: ENSEMBLE SUPERIORITY CONFIRMED. Fusion out-performs individual models.")
    
    print("="*60)

if __name__ == "__main__":
    run_chronological_analysis()
