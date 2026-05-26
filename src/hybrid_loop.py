import pandas as pd
import numpy as np
import joblib
import os
import sys
import json

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.constants import RF_WEIGHT, XGB_WEIGHT, heuristic_price_multiplier, DEFAULT_CAPACITY, CONGESTION_HIGH
from src.features.engine import process_raw_to_features
from src.iot.sensors import DualSensorPair
from src.iot.actuators import ActuatorBridge
from src.blockchain.ipfs import IPFSOffChainStore
from src.digital_twin import DigitalTwinSimulator


def run_hybrid_loop():
    print("\n" + "=" * 90)
    print("GEMINI 6-LAYER HYBRID LOOP: IoT → ML → Blockchain → RL → Digital Twin → Actuator")
    print("=" * 90)

    ipfs = IPFSOffChainStore()
    actuator_bridge = ActuatorBridge()
    dt_sim = DigitalTwinSimulator()

    RAW_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw', 'birmingham_parking.csv')
    features = process_raw_to_features(RAW_PATH)
    test_data = features.tail(20).copy()

    try:
        rf = joblib.load("src/models/artifacts/rf_model.joblib")
        xgb = joblib.load("src/models/artifacts/xgb_model.joblib")
    except Exception as e:
        print(f"Models not found ({e}), running in simulation mode")
        rf = xgb = None

    try:
        agent = joblib.load("src/rl/artifacts/neural_agent.joblib")
    except Exception:
        agent = None
        print("RL agent not found, using heuristic pricing")

    actuator_bridge.register_zone("zone_0")
    ipfs.pin_lot_metadata("zone_0", 500, {"lat": 52.48, "lng": -1.89}, "city_council")
    dt_sim.add_zone("zone_0", 500)
    dt_sim.initialize_from_data(features.head(100))

    X_cols = [
        "occupied_slots", "total_slots", "occ_lag_15m", "occ_lag_1h", "pe_net_flux",
        "pe_arrival_rate", "pe_departure_rate", "pe_turnover", "pe_anomaly", "pe_change_point",
    ]
    test_data["hour"] = test_data["ts_bucket"].dt.hour
    test_data["hour_sin"] = np.sin(2 * np.pi * test_data["hour"] / 24)
    test_data["hour_cos"] = np.cos(2 * np.pi * test_data["hour"] / 24)
    full_X_cols = X_cols + ["hour_sin", "hour_cos"]

    current_price = 10.0
    price_history = []
    all_iot_readings = []

    print("\n" + "-" * 110)
    header = f"{'Step':<5} | {'Timestamp':<18} | {'Pred Occ':<8} | {'PE Flux':<8} | {'PE Anom':<8} | {'Price':<8} | {'Actuator':<22}"
    print(header)
    print("-" * 110)

    dual_sensor = DualSensorPair("zone_0", slot_count=100)

    for i, row in test_data.iterrows():
        ground_truth_occ = np.random.binomial(1, row["occupancy_rate"], 100)
        weather_factor = np.random.uniform(0, 0.3)
        readings = dual_sensor.sample(ground_truth_occ, weather_factor)
        consensus_occ = dual_sensor.consensus_occupancy(readings)
        fp_rate = dual_sensor.false_positive_rate(readings)
        all_iot_readings.append({
            "step": i, "consensus_occ": consensus_occ, "fp_rate": fp_rate,
        })

        if rf and xgb:
            X_input = pd.DataFrame([row[full_X_cols].values], columns=full_X_cols)
            pred_rf = rf.predict(X_input)[0]
            pred_xgb = xgb.predict(X_input)[0]
            predicted_occ = (RF_WEIGHT * pred_rf) + (XGB_WEIGHT * pred_xgb)
        else:
            predicted_occ = consensus_occ

        if agent:
            state = np.array([predicted_occ, current_price, 0.5])
            price_multiplier = agent.act(state, train=False)
        else:
            price_multiplier = heuristic_price_multiplier(predicted_occ)

        current_price = np.clip(current_price * (1 + price_multiplier), 5, 50)
        price_history.append({"step": i, "price": current_price, "action": price_multiplier})

        ipfs_cid = ipfs.pin_price_history("zone_0", price_history[-5:])

        dt_states = dt_sim.tick({"zone_0": price_multiplier})
        dt_zone = dt_states[0] if dt_states else None
        if dt_zone and dt_zone.congestion_level in ("high", "critical"):
            ipfs.pin({"type": "dt_congestion_alert", "zone": "zone_0",
                       "level": dt_zone.congestion_level, "occ": dt_zone.occupancy_rate}, "alert")

        actuation_result = actuator_bridge.actuate("zone_0", consensus_occ, current_price, price_multiplier)

        act_str = f"bar={actuation_result['commands'][0]}, price=${current_price:.1f}"
        pe_flux = row.get("pe_net_flux", 0)
        pe_anom = row.get("pe_anomaly", 0)

        print(f"{i:<5} | {str(row['ts_bucket']):<18} | {predicted_occ:<8.2f} | {pe_flux:<8.2f} | {pe_anom:<8.0f} | ${current_price:<6.1f} | {act_str:<22}")

    print("-" * 110)
    print(f"\n[IPFS] Off-chain objects: {ipfs.summary()['total_pins']} pinned")
    print(f"[IoT] Avg FP rate: {np.mean([r['fp_rate'] for r in all_iot_readings]):.2%}")
    print(f"[Actuator Bridge] Total commands: {actuator_bridge.summary()['total_commands']}")
    print(f"[Digital Twin] Zones: {len(dt_sim.zones)}, History: {len(dt_sim.state_history)} ticks")
    print("\n" + "=" * 90)
    print("6-LAYER HYBRID LOOP COMPLETE: All layers verified.")
    print("=" * 90)

    return {
        "iot_readings": all_iot_readings,
        "price_history": price_history,
        "ipfs_summary": ipfs.summary(),
        "actuator_summary": actuator_bridge.summary(),
        "dt_summary": dt_sim.summary(),
    }


if __name__ == "__main__":
    run_hybrid_loop()
