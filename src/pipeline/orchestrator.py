import numpy as np
import pandas as pd
import os
import hashlib
import threading
import logging
from datetime import datetime, timezone
from typing import Optional

from src.api.database import OccupancyRecord
from src.blockchain.ledger import BlockchainLedger
from src.blockchain.ipfs import IPFSOffChainStore
from src.iot.sensors import DualSensorPair
from src.iot.actuators import ActuatorBridge
from src.digital_twin.simulator import DigitalTwinSimulator
from src.digital_twin.scenario import ScenarioEngine
from src.constants import DEFAULT_CAPACITY, DEFAULT_OCCUPANCY, LAG_15M_DECAY, LAG_1H_DECAY, cyclical_time_features, SENSORS_PER_LOT_DIVISOR, MIN_SENSORS
from src.pipeline.predictor import Predictor
from src.pipeline.pricing import PricingController

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    def __init__(self):
        self._lock = threading.Lock()
        self.predictor = Predictor()
        self.pricing = PricingController()
        self.dt = DigitalTwinSimulator()
        self.scenario_engine = ScenarioEngine()
        self.scenario_engine.register_defaults()
        bc_path = os.getenv("BLOCKCHAIN_PATH", "data/blockchain.json")
        self.ledger = BlockchainLedger.load_from_file(bc_path)
        self.bc_path = bc_path
        self.ipfs = IPFSOffChainStore()
        self.actuator = ActuatorBridge()

    def _ensure_models(self):
        self.predictor.ensure()
        self.pricing.ensure()

    def _predict_occupancy(self, features: pd.Series) -> float:
        return self.predictor.predict(features)

    def _get_rl_price(self, occupancy: float, current_price: float, price_cap: float = 200.0) -> tuple:
        return self.pricing.get_price(occupancy, current_price, price_cap)

    def _predict_price(self, features, current_price, price_cap=200.0):
        predicted_occ = self._predict_occupancy(features)
        new_price, multiplier = self._get_rl_price(predicted_occ, current_price, price_cap)
        return predicted_occ, new_price, multiplier

    def _slot_op(self, slot, target_state):
        if slot is None:
            return
        try:
            from src.micro.state_engine import slot_state_engine, SlotState
            target = SlotState.OCCUPIED if target_state == "occupied" else SlotState.AVAILABLE
            if target_state == "occupied" and slot_state_engine.get_state(slot) == SlotState.OCCUPIED:
                logger.warning("Slot %s already occupied", slot)
                return
            slot_state_engine.set_state(slot, target)
        except ImportError:
            logger.warning("State engine unavailable, skipping %s set", target_state)
        except Exception as e:
            logger.warning("Failed to set slot %s %s: %s", slot, target_state, e)

    def _pin_tx(self, pin_data, content_type, tx_data):
        cid = None
        try:
            cid = self.ipfs.pin(pin_data, content_type=content_type)
        except Exception as e:
            logger.warning("event=ipfs.pin_failed content_type=%s error=%s", content_type, e)
        tx_data["ipfs_cid"] = cid
        self.ledger.add_transaction(tx_data)
        return cid

    def driver_search_lots(self, lots_data: list) -> list:
        self._ensure_models()
        results = []
        for lot in lots_data:
            occ = lot.get("current_occupancy", DEFAULT_OCCUPANCY)
            cf = cyclical_time_features()
            features = pd.Series({
                "occupancy_rate": occ,
                "occupied_slots": occ * lot.get("total_slots", DEFAULT_CAPACITY),
                "total_slots": lot.get("total_slots", DEFAULT_CAPACITY),
                "occ_lag_15m": lot.get("occ_lag_15m", occ * LAG_15M_DECAY),
                "occ_lag_1h": lot.get("occ_lag_1h", occ * LAG_1H_DECAY),
                "pe_net_flux": lot.get("pe_net_flux", 0.0),
                **cf,
                "pe_arrival_rate": 0.0, "pe_departure_rate": 0.0,
                "pe_turnover": 0.0, "pe_anomaly": 0.0, "pe_change_point": 0.0,
                "occ_roll_mean_3h": occ, "occ_roll_std_3h": 0.0, "occ_acceleration": 0.0,
            })
            predicted_occ, new_price, _ = self._predict_price(features, lot.get("current_price", 10), lot.get("price_cap", 200.0))
            available = int(lot.get("total_slots", 500) * (1 - predicted_occ))
            results.append({
                "lot_id": lot.get("lot_id", ""),
                "name": lot.get("name", ""),
                "address": lot.get("address", ""),
                "city": lot.get("city", ""),
                "total_slots": lot.get("total_slots", 0),
                "predicted_occupancy": round(predicted_occ, 3),
                "available_spots": max(available, 0),
                "dynamic_price": round(new_price, 2),
                "base_price": lot.get("base_price", 10),
                "latitude": lot.get("latitude"),
                "longitude": lot.get("longitude"),
                "available_handicap": lot.get("available_handicap", 0),
                "available_ev": lot.get("available_ev", 0),
                "available_regular": lot.get("available_regular", 0),
            })
        return sorted(results, key=lambda x: x["available_spots"], reverse=True)

    def start_session(self, lot_id: str, driver_id: str, slot: int = 0,
                      total_slots: int = 500, base_price: float = 10.0,
                      current_price: Optional[float] = None, price_cap: float = 200.0,
                      features: Optional[pd.Series] = None) -> dict:
        with self._lock:
            session_id = hashlib.sha256(os.urandom(32)).hexdigest()[:16]
            timestamp = datetime.now(timezone.utc).isoformat()

            sensor = DualSensorPair(lot_id, slot_count=max(total_slots // SENSORS_PER_LOT_DIVISOR, MIN_SENSORS))
            weather = np.random.uniform(0, 0.3)
            gt = np.random.binomial(1, 0.5, max(total_slots // SENSORS_PER_LOT_DIVISOR, MIN_SENSORS))
            readings = sensor.sample(gt, weather_factor=weather)
            consensus_occ = sensor.consensus_occupancy(readings)
            fp_rate = sensor.false_positive_rate(readings)

            if features is not None:
                features = features.copy()
                features["occupancy_rate"] = consensus_occ
                predicted_occ = self._predict_occupancy(features)
            else:
                predicted_occ = consensus_occ

            live_price = current_price if current_price is not None else base_price
            self._slot_op(slot, "occupied")
            new_price, multiplier = self._get_rl_price(predicted_occ, live_price, price_cap)

            pin_data = {
                "type": "session_start", "session_id": session_id,
                "lot_id": lot_id, "driver_id": driver_id, "slot": slot,
                "timestamp": timestamp, "predicted_occ": predicted_occ,
                "weather_factor": round(weather, 4),
            }
            tx_data = {
                "type": "session_start", "session_id": session_id,
                "lot_id": lot_id, "driver_id": driver_id,
                "action": "session_fee", "price_at_entry": round(new_price, 2),
            }
            ipfs_cid = self._pin_tx(pin_data, "session", tx_data)
            dt_summary = self.dt.summary()
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
                    entry_price: float, total_slots: int = 500, price_cap: float = 200.0,
                    slot: int = 0) -> dict:
        with self._lock:
            end_time = datetime.now(timezone.utc)
            try:
                start_dt = datetime.fromisoformat(start_time)
                if start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=timezone.utc)
                duration_hours = max((end_time - start_dt).total_seconds() / 3600, 0.1)
            except (ValueError, TypeError):
                logger.exception("Invalid start_time %s", start_time)
                duration_hours = 1.0

            occ = current_occupancy
            final_price, _ = self._get_rl_price(occ, entry_price, price_cap)
            amount = round(final_price * duration_hours, 2)
            amount = min(amount, price_cap * 24)

            pin_data = {
                "type": "session_end", "session_id": session_id,
                "lot_id": lot_id, "driver_id": driver_id,
                "duration_hours": round(duration_hours, 2), "amount": amount,
                "entry_price": entry_price, "final_price": final_price,
                "timestamp": end_time.isoformat(),
            }
            tx_data = {
                "type": "payment", "session_id": session_id,
                "lot_id": lot_id, "driver_id": driver_id,
                "action": "session_fee", "amount": amount,
                "entry_price": entry_price, "final_price": final_price,
            }
            ipfs_cid = self._pin_tx(pin_data, "payment", tx_data)
            self._slot_op(slot, "available")
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
                "layers_activated": ["iot", "ml", "blockchain", "rl", "digital_twin", "actuator"],
            }

    def process_payment(self, session_id: str, driver_id: str,
                        amount: float, lot_id: str) -> dict:
        with self._lock:
            tx_hash = hashlib.sha256(os.urandom(32)).hexdigest()[:16]
            pin_data = {
                "type": "payment_confirmation", "session_id": session_id,
                "driver_id": driver_id, "amount": amount, "lot_id": lot_id,
                "tx_hash": tx_hash, "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            tx_data = {
                "type": "payment_confirmation", "session_id": session_id,
                "driver_id": driver_id, "lot_id": lot_id,
                "action": "session_fee", "amount": amount,
                "tx_hash": tx_hash,
            }
            ipfs_cid = self._pin_tx(pin_data, "payment_confirmation", tx_data)
            return {
                "session_id": session_id,
                "tx_hash": tx_hash,
                "amount": amount,
                "blockchain_ref": ipfs_cid,
                "ledger_blocks": len(self.ledger.chain),
            }

    def run_digital_twin_scenario(self, scenario_type: str = "zone_closure",
                                   zone_id: str = "zone_0") -> dict:
        base_state = self.dt.get_zone_state(zone_id) or {
            "zone_id": zone_id, "occupancy_rate": DEFAULT_OCCUPANCY, "price": 10.0,
            "total_slots": DEFAULT_CAPACITY, "available_slots": 250, "congestion_level": "normal",
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

    def add_ledger_transaction(self, tx: dict) -> int:
        with self._lock:
            return self.ledger.add_transaction(tx)

    def mine_ledger(self) -> dict:
        with self._lock:
            block = self.ledger.mine_pending()
            self.ledger.save_to_file(self.bc_path)
            return {
                "block_index": block.index,
                "hash": block.hash,
                "transactions": len(block.transactions),
                "nonce": block.nonce,
                "timestamp": block.timestamp,
            }

    def flush_ledger(self) -> bool:
        try:
            if self.ledger.pending_transactions:
                self.mine_ledger()
            return True
        except Exception:
            logger.exception("event=ledger.flush.failed")
            try:
                self.ledger = BlockchainLedger.load_from_file(self.bc_path)
                logger.info("event=ledger.flush.reload.completed")
            except Exception:
                logger.exception("event=ledger.flush.reload.failed")
            return False

    def simulate_ingest(self, db_session, lot) -> dict:
        latest = db_session.query(OccupancyRecord).filter(
            OccupancyRecord.lot_id == lot.lot_id
        ).order_by(OccupancyRecord.timestamp.desc()).first()
        drift = np.random.normal(0, 0.02)
        new_occ = max(0.0, min(1.0, (latest.occupancy_rate if latest else 0.3) + (drift if latest else 0)))
        new_price, _ = self._get_rl_price(new_occ, float(latest.price) if latest else float(lot.base_price), float(lot.price_cap))
        return {
            "lot_id": lot.lot_id,
            "occupied_slots": int(new_occ * lot.total_slots),
            "total_slots": lot.total_slots,
            "occupancy_rate": round(new_occ, 4),
            "pe_net_flux": 0.0,
            "price": round(new_price, 2),
        }

    def status(self) -> dict:
        with self._lock:
            return {
                "ml_models": self.predictor.summary,
                "rl_agent": self.pricing.agent_available,
                "blockchain": {
                    "chain_length": len(self.ledger.chain),
                    "pending_tx": len(self.ledger.pending_transactions),
                },
                "digital_twin": self.dt.summary(),
                "actuator": self.actuator.summary(),
            }


pipeline = PipelineOrchestrator()
