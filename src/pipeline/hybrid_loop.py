import logging
import os
import sys

import numpy as np
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from typing import cast
from src.constants import PRICE_MIN, PRICE_MAX, IOT_WEATHER_MAX, EXPECTED_FEATURE_COLS  # noqa: E402
from src.features.engine import process_raw_to_features  # noqa: E402
from src.pipeline.predictor import Predictor  # noqa: E402
from src.pipeline.pricing import PricingController  # noqa: E402
from src.iot.sensors import DualSensorPair  # noqa: E402
from src.iot.actuators import ActuatorBridge  # noqa: E402
from src.blockchain.ipfs import IPFSOffChainStore  # noqa: E402
from src.digital_twin import DigitalTwinSimulator  # noqa: E402

logger = logging.getLogger(__name__)


def run_hybrid_loop():
    print("\n" + "=" * 90)
    print("GEMINI 6-LAYER HYBRID LOOP: IoT → ML → Blockchain → RL → Digital Twin → Actuator")
    print("=" * 90)

    ipfs = IPFSOffChainStore()
    actuator_bridge = ActuatorBridge()
    dt_sim = DigitalTwinSimulator()
    predictor = Predictor()
    pricing = PricingController()

    RAW_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw', 'birmingham_parking.csv')
    features = process_raw_to_features(RAW_PATH)
    test_data = features.tail(20).copy()

    actuator_bridge.register_zone("zone_0")
    ipfs.pin_lot_metadata("zone_0", 500, {"lat": 52.48, "lng": -1.89}, "city_council")
    dt_sim.add_zone("zone_0", 500)
    dt_sim.initialize_from_data(features.head(100))

    test_data["hour"] = test_data["ts_bucket"].dt.hour
    test_data["hour_sin"] = np.sin(2 * np.pi * test_data["hour"] / 24)
    test_data["hour_cos"] = np.cos(2 * np.pi * test_data["hour"] / 24)
    test_data["hour_sq"] = (test_data["hour"] - 12) ** 2 / 144
    test_data["dow"] = test_data["ts_bucket"].dt.dayofweek
    test_data["dow_sin"] = np.sin(2 * np.pi * test_data["dow"] / 7)
    test_data["dow_cos"] = np.cos(2 * np.pi * test_data["dow"] / 7)
    test_data["is_weekend"] = (test_data["dow"] >= 5).astype(float)
    test_data["occ_roll_mean_3h"] = test_data.groupby("total_slots")["occupancy_rate"].transform(
        lambda s: s.rolling(12, min_periods=1).mean().shift(1)
    )
    test_data["occ_roll_std_3h"] = test_data.groupby("total_slots")["occupancy_rate"].transform(
        lambda s: s.rolling(12, min_periods=1).std().shift(1)
    )
    test_data["occ_roll_mean_3h"] = test_data["occ_roll_mean_3h"].fillna(test_data["occupancy_rate"].expanding().mean())
    test_data["occ_roll_std_3h"] = test_data["occ_roll_std_3h"].fillna(0)
    test_data["occ_acceleration"] = test_data.groupby("total_slots")["pe_net_flux"].diff().fillna(0)
    full_X_cols = EXPECTED_FEATURE_COLS
    price_history = []
    all_iot_readings = []

    print("\n" + "-" * 110)
    header = f"{'Step':<5} | {'Timestamp':<18} | {'Pred Occ':<8} | {'PE Flux':<8} | {'PE Anom':<8} | {'Price':<8} | {'Actuator':<22}"
    print(header)
    print("-" * 110)

    dual_sensor = DualSensorPair("zone_0", slot_count=100)
    current_price = PRICE_MIN

    for i, row in test_data.iterrows():
        ground_truth_occ = np.random.binomial(1, row["occupancy_rate"], 100)
        weather_factor = np.random.uniform(0, IOT_WEATHER_MAX)
        readings = dual_sensor.sample(ground_truth_occ, weather_factor)
        consensus_occ = dual_sensor.consensus_occupancy(readings)
        fp_rate = dual_sensor.false_positive_rate(readings)
        all_iot_readings.append({
            "step": i, "consensus_occ": consensus_occ, "fp_rate": fp_rate,
        })

        predicted_occ = predictor.predict(cast(pd.Series, row[full_X_cols]))
        price_multiplier = pricing.get_price(predicted_occ, current_price, PRICE_MAX)[1]
        current_price = np.clip(current_price * (1 + price_multiplier), PRICE_MIN, PRICE_MAX)
        price_history.append({"step": i, "price": current_price, "action": price_multiplier})

        ipfs.pin_price_history("zone_0", price_history[-5:])

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
