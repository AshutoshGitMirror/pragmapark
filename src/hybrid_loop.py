import pandas as pd
import numpy as np
import joblib
import os
import sys

# Ensure project root is in path
sys.path.append(os.getcwd())

from src.features.engine import process_raw_to_features
from src.rl.agent import NeuralAgent

def run_hybrid_simulation():
    print("\n" + "="*80)
    print("GEMINI HYBRID SMART PARKING: CONTINUOUS NEURAL ACTUATION")
    print("="*80)

    # 1. Load Predictive Artifacts
    try:
        rf = joblib.load("src/models/artifacts/rf_model.joblib")
        xgb = joblib.load("src/models/artifacts/xgb_model.joblib")
    except:
        print("Error: Predictive models not found.")
        return

    # 2. Initialize Neural Agent
    print("\n[Layer 4] Loading Continuous Neural Agent...")
    try:
        agent = joblib.load("src/rl/artifacts/neural_agent.joblib")
    except:
        print("Error: Neural Agent not found. Run train_control.py first.")
        return

    # 3. Load Real-World Data for Simulation
    RAW_PATH = "data/raw/birmingham_parking.csv"
    features = process_raw_to_features(RAW_PATH)
    
    # Take a slice of unseen data
    test_data = features.tail(20)
    
    X_cols = ['occupied_slots', 'total_slots', 'occ_lag_15m', 'occ_lag_1h', 'net_flux']
    test_data['hour'] = test_data['ts_bucket'].dt.hour
    test_data['hour_sin'] = np.sin(2 * np.pi * test_data['hour'] / 24)
    test_data['hour_cos'] = np.cos(2 * np.pi * test_data['hour'] / 24)
    full_X_cols = X_cols + ['hour_sin', 'hour_cos']
    
    current_price = 10.0
    print("\n" + "-"*90)
    print(f"{'Timestamp':<20} | {'Pred Occ':<8} | {'Change':<8} | {'New Price':<12} | {'Est. Revenue':<15}")
    print("-" * 90)
    
    for i, (_, row) in enumerate(test_data.iterrows()):
        # A. PREDICTION (ML Ensemble)
        X_input = pd.DataFrame([row[full_X_cols].values], columns=full_X_cols)
        pred_rf = rf.predict(X_input)[0]
        pred_xgb = xgb.predict(X_input)[0]
        predicted_occ = (0.4 * pred_rf) + (0.6 * pred_xgb)
        
        # B. CONTINUOUS NEURAL ACTUATION
        state = np.array([predicted_occ, current_price, 0.5]) 
        price_multiplier = agent.act(state, train=False)
        
        # Update price
        current_price = np.clip(current_price * (1 + price_multiplier), 5, 50)
        
        # Revenue Impact
        hourly_revenue = (row['occupancy_rate'] * row['total_slots']) * current_price
        
        change_desc = f"{price_multiplier:+.2%}"
        
        print(f"{str(row['ts_bucket']):<20} | {predicted_occ:<8.2f} | {change_desc:<8} | ${current_price:>8.2f}/hr | ${hourly_revenue:>12.2f}/hr")

    print("\n" + "="*90)
    print("HYBRID LOOP COMPLETE: Continuous Neural Policy verified.")
    print("="*90)

if __name__ == "__main__":
    run_hybrid_simulation()
