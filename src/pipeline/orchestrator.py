import numpy as np
import pandas as pd
import joblib
import os
import hashlib
import threading
import logging
from datetime import datetime, timezone
from typing import Optional

from src.blockchain.ledger import BlockchainLedger
from src.blockchain.ipfs import IPFSOffChainStore
from src.iot.sensors import DualSensorPair
from src.iot.actuators import ActuatorBridge
from src.digital_twin.simulator import DigitalTwinSimulator
from src.digital_twin.scenario import ScenarioEngine
from src.features.builder import safe_predict, X_COLS

logger = logging.getLogger(__name__)
MODEL_DIR = os.getenv("MODEL_ARTIFACT_PATH", "src/models/artifacts")

class PipelineOrchestrator:
    def __init__(self):
        self._lock = threading.Lock()
        self.rf = None
        self.xgb = None
        self.meta = None
        self.agent = None
        self.dt = DigitalTwinSimulator()
        self.scenario_engine = ScenarioEngine()
        self.scenario_engine.register_defaults()
        self.ledger = BlockchainLedger()
        self.ipfs = IPFSOffChainStore()
        self.actuator = ActuatorBridge()
        self._load_models()

    def _load_models(self):
        rf_path = os.path.join(MODEL_DIR, "rf_model.joblib")
        xgb_path = os.path.join(MODEL_DIR, "xgb_model.joblib")
        meta_path = os.path.join(MODEL_DIR, "meta_model.joblib")
        agent_path = "src/rl/artifacts/neural_agent.joblib"
        for path, attr in [(rf_path, "rf"), (xgb_path, "xgb"), (meta_path, "meta")]:
            try:
                setattr(self, attr, joblib.load(path))
                logger.info(f"Loaded {attr} model from {path}")
            except Exception as e:
                logger.warning(f"Failed to load {attr}: {e}")
                setattr(self, attr, None)
        try:
            self.agent = joblib.load(agent_path)
            logger.info(f"Loaded RL agent from {agent_path}")
        except Exception as e:
            logger.warning(f"Failed to load RL agent: {e}")
            self.agent = None

    def _predict_occupancy(self, features: pd.Series) -> float:
        if self.rf is None or self.xgb is None:
            return float(features.get("occupancy_rate", features.get("occ_lag_15m", 0.5)))
        def ensemble(X: pd.DataFrame) -> float:
            pred_rf = float(self.rf.predict(X)[0])
            pred_xgb = float(self.xgb.predict(X)[0])
            if not np.isfinite(pred_rf) or not np.isfinite(pred_xgb):
                logger.warning(f"Non-finite prediction: rf={pred_rf}, xgb={pred_xgb}")
                return 0.5
            if self.meta is not None:
                meta_in = np.array([[pred_rf, pred_xgb]])
                pred = float(self.meta.predict(meta_in)[0])
            else:
                pred = 0.4 * pred_rf + 0.6 * pred_xgb
            return float(np.clip(pred, 0.0, 1.0))
        return safe_predict(ensemble, features)

    def _get_rl_price(self, occupancy: float, current_price: float) -> tuple:
        if self.agent:
            self.agent.epsilon = 0.0
            state = np.array([occupancy, current_price, 0.5])
            multiplier = float(self.agent.act(state, train=False))
        else:
            if occupancy > 0.8:
                multiplier = 0.15
            elif occupancy < 0.4:
                multiplier = -0.1
            else:
                multiplier = 0.0
        new_price = np.clip(current_price * (1 + multiplier), 5, 50)
        return new_price, multiplier

    def driver_search_lots(self, lots_data: list) -> list:
        results = []
        for lot in lots_data:
            occ = lot.get("current_occupancy", 0.5)
            new_price, _ = self._get_rl_price(occ, lot.get("current_price", 10))
            available = int(lot.get("total_slots", 0) * (1 - occ))
            results.append({
                "lot_id": lot["lot_id"],
                "name": lot["name"],
                "address": lot.get("address", ""),
                "predicted_occupancy": round(occ, 3),
                "available_spots": max(available, 0),
                "dynamic_price": round(new_price, 2),
                "base_price": lot.get("base_price", 10),
            })
        return sorted(results, key=lambda x: x["available_spots"], reverse=True)

    def start_session(self, lot_id: str, driver_id: str, slot: int = 0,
                      total_slots: int = 500, base_price: float = 10.0,
                      features: Optional[pd.Series] = None) -> dict:
        with self._lock:
            session_id = hashlib.sha256(os.urandom(32)).hexdigest()[:16]
            timestamp = datetime.now(timezone.utc).isoformat()

            sensor = DualSensorPair(lot_id, slot_count=max(total_slots // 50, 5))
            weather = np.random.uniform(0, 0.3)
            gt = np.random.binomial(1, 0.5, max(total_slots // 50, 5))
            readings = sensor.sample(gt, weather_factor=weather)
            consensus_occ = sensor.consensus_occupancy(readings)
            fp_rate = sensor.false_positive_rate(readings)

            if features is not None:
                features["occupancy_rate"] = consensus_occ
                predicted_occ = self._predict_occupancy(features)
            else:
                predicted_occ = consensus_occ

            current_price = base_price
            new_price, multiplier = self._get_rl_price(predicted_occ, current_price)

            ipfs_cid = self.ipfs.pin({
                "type": "session_start", "session_id": session_id,
                "lot_id": lot_id, "driver_id": driver_id, "slot": slot,
                "timestamp": timestamp, "predicted_occ": predicted_occ,
                "weather_factor": round(weather, 4),
            }, "session")
            tx = {
                "type": "session_start", "session_id": session_id,
                "lot_id": lot_id, "driver_id": driver_id,
                "action": "park", "price_at_entry": round(new_price, 2),
                "ipfs_cid": ipfs_cid,
            }
            self.ledger.add_transaction(tx)
            self.ledger.mine_pending()

            if lot_id not in self.dt.zones:
                self.dt.add_zone(lot_id, total_slots)
            dt_states = self.dt.tick({lot_id: multiplier})
            dt_summary = self.dt.get_zone_state(lot_id) if lot_id in self.dt.zones else None

            self.actuator.register_zone(lot_id)
            self.actuator.actuate(lot_id, predicted_occ, new_price, multiplier)

            return {
                "session_id": session_id,
                "lot_id": lot_id,
                "driver_id": driver_id,
                "slot": slot,
                "start_time": timestamp,
                "predicted_occupancy": round(predicted_occ, 3),
                "price_at_entry": round(new_price, 2),
                "base_price": round(base_price, 2),
                "price_multiplier": round(multiplier, 4),
                "blockchain_ref": ipfs_cid,
                "iot_consensus": round(consensus_occ, 3),
                "iot_fp_rate": round(fp_rate, 4),
                "weather_factor": round(weather, 4),
                "digital_twin": dt_summary,
                "layers_activated": ["iot", "ml", "blockchain", "rl", "digital_twin", "actuator"],
            }

    def end_session(self, session_id: str, lot_id: str, driver_id: str,
                    start_time: str, current_occupancy: float,
                    entry_price: float, total_slots: int = 500) -> dict:
        with self._lock:
            end_time = datetime.now(timezone.utc)
            try:
                start_dt = datetime.fromisoformat(start_time)
                duration_hours = max((end_time - start_dt).total_seconds() / 3600, 0.1)
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid start_time {start_time}: {e}")
                duration_hours = 1.0

            occ = current_occupancy
            final_price, _ = self._get_rl_price(occ, entry_price)
            amount = round(final_price * duration_hours, 2)

            ipfs_cid = self.ipfs.pin({
                "type": "session_end", "session_id": session_id,
                "lot_id": lot_id, "driver_id": driver_id,
                "duration_hours": round(duration_hours, 2), "amount": amount,
                "entry_price": entry_price, "final_price": final_price,
                "timestamp": end_time.isoformat(),
            }, "payment")
            tx = {
                "type": "payment", "session_id": session_id,
                "lot_id": lot_id, "driver_id": driver_id,
                "action": "payment", "amount": amount,
                "entry_price": entry_price, "final_price": final_price,
                "ipfs_cid": ipfs_cid,
            }
            self.ledger.add_transaction(tx)
            self.ledger.mine_pending()

            sensor = DualSensorPair(lot_id, slot_count=1)
            sensor.sample(np.array([False]))

            if lot_id in self.dt.zones:
                self.dt.tick({lot_id: -0.05})
            self.actuator.actuate(lot_id, occ, final_price, -0.05)

            return {
                "session_id": session_id,
                "lot_id": lot_id,
                "driver_id": driver_id,
                "duration_hours": round(duration_hours, 2),
                "entry_price": round(entry_price, 2),
                "final_price": round(final_price, 2),
                "amount_charged": amount,
                "blockchain_ref": ipfs_cid,
                "end_time": end_time.isoformat(),
                "layers_activated": ["iot", "ml", "rl", "blockchain", "digital_twin", "actuator"],
            }

    def process_payment(self, session_id: str, driver_id: str,
                        amount: float, lot_id: str) -> dict:
        with self._lock:
            tx_hash = hashlib.sha256(os.urandom(32)).hexdigest()[:16]
            ipfs_cid = self.ipfs.pin({
                "type": "payment_confirmation", "session_id": session_id,
                "driver_id": driver_id, "amount": amount, "lot_id": lot_id,
                "tx_hash": tx_hash, "timestamp": datetime.now(timezone.utc).isoformat(),
            }, "payment_confirmation")
            tx = {
                "type": "payment_confirmation", "session_id": session_id,
                "driver_id": driver_id, "lot_id": lot_id,
                "action": "payment", "amount": amount,
                "tx_hash": tx_hash, "ipfs_cid": ipfs_cid,
            }
            self.ledger.add_transaction(tx)
            self.ledger.mine_pending()

            return {
                "status": "confirmed",
                "session_id": session_id,
                "tx_hash": tx_hash,
                "amount": amount,
                "blockchain_ref": ipfs_cid,
                "ledger_blocks": len(self.ledger.chain),
            }

    def run_digital_twin_scenario(self, scenario_type: str = "zone_closure",
                                   zone_id: str = "zone_0") -> dict:
        base_state = self.dt.get_zone_state(zone_id) or {
            "zone_id": zone_id, "occupancy_rate": 0.5, "price": 10.0,
            "total_slots": 500, "available_slots": 250, "congestion_level": "normal",
        }
        results = self.scenario_engine.run_all(base_state)
        comparisons = self.scenario_engine.compare(base_state)
        scenario_data = None
        for r in results:
            if r["scenario"] == scenario_type:
                scenario_data = r
                break
        return {
            "scenario": scenario_type,
            "zone_id": zone_id,
            "result": scenario_data,
            "all_scenarios": results,
            "comparisons": comparisons,
        }

    def status(self) -> dict:
        with self._lock:
            return {
            "ml_models": {"rf": self.rf is not None, "xgb": self.xgb is not None},
            "rl_agent": self.agent is not None,
            "blockchain": {
                "chain_length": len(self.ledger.chain),
                "pending_tx": len(self.ledger.pending_transactions),
            },
            "digital_twin": self.dt.summary(),
            "actuator": self.actuator.summary(),
        }

pipeline = PipelineOrchestrator()
