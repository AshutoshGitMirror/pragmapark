import numpy as np
import pandas as pd
import os
import hashlib
import logging
from datetime import datetime, timezone
from src.api.database import OccupancyRecord, get_db_cm, MicroSlot
from src.api.utils import DBLock
from src.blockchain.ledger import BlockchainLedger
from src.blockchain.ipfs import IPFSOffChainStore
from src.blockchain.contract import RevenueShareContract, AllocationContract, ShareSettlementContract
from src.blockchain.pool_manager import pool_manager
from src.iot.sensors import DualSensorPair
from src.iot.generator import RealisticParkingSensorSimulator
from src.iot.actuators import ActuatorBridge
from src.digital_twin.simulator import DigitalTwinSimulator
from src.digital_twin.scenario import ScenarioEngine
from src.rl.multi_agent import QMIXMARL
from src.micro.state_engine import slot_state_engine, SlotState
from src.micro.resident_map import slot_resident_mapping
from src.constants import (
    DEFAULT_CAPACITY, DEFAULT_OCCUPANCY,
    LAG_15M_DECAY, LAG_1H_DECAY, cyclical_time_features,
    SENSORS_PER_LOT_DIVISOR, MIN_SENSORS,
)
from src.pipeline.predictor import Predictor
from src.pipeline.pricing import PricingController

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    def __init__(self):
        self._lock = DBLock()
        self.predictor = Predictor()
        self.marl = None
        self.pricing = PricingController(marl=None)
        self._scenario_engine = None
        self.dt = DigitalTwinSimulator()
        bc_path = os.getenv("BLOCKCHAIN_PATH", "data/blockchain.json")
        self.bc_path = bc_path
        self._ledger = None
        self.ipfs = IPFSOffChainStore()
        self.actuator = ActuatorBridge()
        self.pool_manager = pool_manager
        self.revenue_contract = RevenueShareContract(
            "revenue_v1", "city",
            {"city": 0.7, "lot_owner": 0.3}, system_fee_ratio=0.15)
        self.allocation_contract = AllocationContract("allocation_v1", "city")
        self.share_settlement_contract = ShareSettlementContract("share_settle_v1", "platform")
        self.sensor_simulators = {}
        self._slot_id_cache: dict[str, dict[int, int]] = {}

    @property
    def scenario_engine(self) -> ScenarioEngine:
        if self._scenario_engine is None:
            self._scenario_engine = ScenarioEngine()
            self._scenario_engine.register_defaults()
        return self._scenario_engine

    @property
    def ledger(self) -> BlockchainLedger:
        if self._ledger is None:
            try:
                self._ledger = BlockchainLedger.load_from_file(self.bc_path)
            except FileNotFoundError:
                self._ledger = BlockchainLedger()
        return self._ledger

    @ledger.setter
    def ledger(self, value: BlockchainLedger) -> None:
        self._ledger = value

    def _ensure_models(self):
        self.predictor.ensure()
        self._ensure_marl()
        self.pricing.ensure()

    def _ensure_marl(self):
        if self.marl is not None:
            return
        try:
            if not self.dt.zones:
                try:
                    self.dt.bootstrap_from_db()
                except Exception as db_err:
                    logger.warning(
                        "event=marl.bootstrap_failed error=%s", db_err)
            zone_ids = list(self.dt.zones.keys()) or [
                            "zone_0", "zone_1", "zone_2"]
            capacities = [
                self.dt.zones[z].get("capacity", 500)
                if isinstance(self.dt.zones.get(z), dict) else 500
                for z in zone_ids
            ]
            self.marl = QMIXMARL(num_zones=len(zone_ids),
                                 zone_capacities=capacities)
            self.pricing.marl = self.marl
        except Exception as e:
            logger.warning("event=marl.init_failed error=%s", e)
            self.marl = None

    def _predict_occupancy(self, features: pd.Series) -> float:
        return self.predictor.predict(features)

    def _get_rl_price(self, occupancy, current_price,
                      price_cap=200.0, zone_id=None):
        return self.pricing.get_price(
            occupancy, current_price, price_cap, zone_id=zone_id)

    def _predict_price(self, features, current_price,
                       price_cap=200.0, zone_id=None):
        pocc = self._predict_occupancy(features)
        np_, mult = self._get_rl_price(
            pocc, current_price, price_cap, zone_id=zone_id)
        return pocc, np_, mult

    def _resolve_slot_id(self, lot_id: str, slot_index: int) -> int | None:
        lot_cache = self._slot_id_cache.get(lot_id)
        if lot_cache is not None:
            sid = lot_cache.get(slot_index)
            if sid is not None:
                return sid
        try:
            with get_db_cm() as db:
                slot = (
                    db.query(MicroSlot)
                    .filter(MicroSlot.lot_id == lot_id,
                            MicroSlot.slot_index == slot_index,
                            MicroSlot.active == 1)
                    .first()
                )
                if slot is not None:
                    self._slot_id_cache.setdefault(
                        lot_id, {})[slot_index] = slot.id
                    return slot.id
        except Exception as e:
            logger.warning("event=resolve_slot_id.failed lot=%s slot=%d error=%s",
                           lot_id, slot_index, e)
        return None

    def _slot_op(self, lot_id: str, slot_index: int, target_state: str):
        if slot_index is None or (isinstance(
            slot_index, int) and slot_index <= 0) or lot_id is None:
            return
        slot_id = self._resolve_slot_id(lot_id, slot_index)
        if slot_id is None:
            return
        target = SlotState.OCCUPIED if target_state == "occupied" else SlotState.AVAILABLE
        if target_state == "occupied" and slot_state_engine.get_state(
            slot_id) == SlotState.OCCUPIED:
            return
        slot_state_engine.set_state(slot_id, target)

    def _pin_tx(self, pin_data, content_type, tx_data):
        try:
            cid = self.ipfs.pin(pin_data, content_type=content_type)
        except Exception as e:
            logger.warning(
                "event=ipfs.pin_failed ct=%s error=%s", content_type, e)
            cid = None
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
                "pe_turnover": 0.0, "pe_anomaly": 0.0,
                "pe_change_point": 0.0, "occ_roll_mean_3h": occ,
                "occ_roll_std_3h": 0.0, "occ_acceleration": 0.0,
                "n_resident_slots": float(slot_resident_mapping.count_resident_only(
                    lot.get("lot_id", ""))),
                "n_active_share_listings": float(sum(
                    1 for s in slot_resident_mapping.get_resident_slots(
                        lot.get("lot_id", ""))
                    if s.is_shared
                )),
            })
            pocc, np_, _ = self._predict_price(
                features, lot.get("current_price", 10),
                lot.get("price_cap", 200.0), zone_id=lot.get("lot_id"))
            # A110: coerce to finite floats so a NaN/None never reaches the
            # response layer (would raise an unlogged validation error -> 500).
            pocc = float(np.nan_to_num(pocc, nan=0.0))
            np_ = float(np.nan_to_num(np_, nan=0.0))
            total_slots = int(np.nan_to_num(lot.get("total_slots", 0), nan=0))
            base_price = float(np.nan_to_num(lot.get("base_price", 0), nan=0))
            available = int(max(total_slots * (1 - pocc), 0))
            results.append({
                "lot_id": lot.get("lot_id", ""), "name": lot.get("name", ""),
                "address": lot.get("address", ""), "city": lot.get("city", ""),
                "total_slots": total_slots,
                "predicted_occupancy": round(pocc, 3),
                "available_spots": available,
                "dynamic_price": round(np_, 2),
                "base_price": base_price,
                "latitude": lot.get("latitude"), "longitude": lot.get("longitude"),
                "available_handicap": lot.get("available_handicap", 0),
                "available_ev": lot.get("available_ev", 0),
                "available_regular": lot.get("available_regular", 0),
            })
        return sorted(
            results, key=lambda x: x["available_spots"], reverse=True)

    def _get_sensor_simulator(self, lot_id, capacity):
        if lot_id not in self.sensor_simulators:
            self.sensor_simulators[lot_id] = RealisticParkingSensorSimulator(
                zone_id=lot_id, capacity=capacity)
        return self.sensor_simulators[lot_id]

    def start_session(self, lot_id, driver_id, slot=0, total_slots=500,
                      base_price=10.0, current_price=None, price_cap=200.0, features=None):
        with self._lock:
            session_id = hashlib.sha256(os.urandom(32)).hexdigest()[:16]
            ts = datetime.now(timezone.utc).isoformat()
            sim_cap = max(total_slots // SENSORS_PER_LOT_DIVISOR, MIN_SENSORS)
            sim = self._get_sensor_simulator(lot_id, sim_cap)
            readings = sim.sample_step(datetime.now(timezone.utc))
            weather = sim.get_weather_factor(datetime.now(timezone.utc))
            sensor = DualSensorPair(lot_id, slot_count=sim_cap)
            fused_occ = float(sensor.clean_reading(readings).mean())
            fp_rate = sensor.false_positive_rate(readings)
            if features is not None:
                features = features.copy()
                features["occupancy_rate"] = fused_occ
                pocc = self._predict_occupancy(features)
            else:
                pocc = fused_occ
            live_price = current_price if current_price is not None else base_price
            self._slot_op(lot_id, slot, "occupied")
            np_, mult = self._get_rl_price(
                pocc, live_price, price_cap, zone_id=lot_id)
            self.actuator.actuate(lot_id, fused_occ, np_, mult)

            try:
                alloc = self.allocation_contract.execute({
                    "driver_id": driver_id, "lot_id": lot_id,
                    "price": np_, "available_spots": [f"slot_{slot}"],
                })
                if alloc.get("allocated"):
                    self.ledger.add_transaction({
                        "type": "allocation", "session_id": session_id,
                        "lot_id": lot_id, "driver_id": driver_id,
                        "action": "spot_allocation",
                        "spot_id": alloc.get("spot_id"),
                        "allocation_key": alloc.get("allocation_key"),
                    })
            except Exception as e:
                logger.warning(
                    "event=allocation.failed session=%s error=%s", session_id, e)

            cid = self._pin_tx(
                {"type": "session_start", "session_id": session_id, "lot_id": lot_id,
                 "driver_id": driver_id, "slot": slot, "timestamp": ts,
                 "predicted_occ": pocc, "weather_factor": round(weather, 4)},
                "session",
                {"type": "session_start", "session_id": session_id, "lot_id": lot_id,
                 "driver_id": driver_id, "action": "session_fee",
                 "price_at_entry": round(np_, 2)})
            return {
                "session_id": session_id, "lot_id": lot_id, "driver_id": driver_id,
                "slot": slot, "start_time": ts,
                "predicted_occupancy": float(round(pocc, 3)),
                "price_at_entry": float(round(np_, 2)),
                "base_price": float(round(base_price, 2)),
                "price_multiplier": float(round(mult, 4)),
                "blockchain_ref": cid,
                "iot_consensus": float(round(fused_occ, 3)),
                "iot_fp_rate": float(round(fp_rate, 4)),
                "weather_factor": float(round(weather, 4)),
                "digital_twin": self.dt.summary(),
                "layers_activated": ["iot", "ml", "blockchain", "rl", "actuator"],
            }

    def end_session(self, session_id, lot_id, driver_id, start_time,
                    current_occupancy, entry_price, total_slots=500,
                    price_cap=200.0, slot=0):
        with self._lock:
            end_time = datetime.now(timezone.utc)
            try:
                sd = datetime.fromisoformat(start_time)
                if sd.tzinfo is None:
                    sd = sd.replace(tzinfo=timezone.utc)
                dur = (end_time - sd).total_seconds() / 3600
            except (ValueError, TypeError):
                dur = 1.0
            cr, _ = self._get_rl_price(
                current_occupancy, entry_price, price_cap, zone_id=lot_id)
            amount = min(round(entry_price * dur, 2), price_cap * 24)
            cid = self._pin_tx(
                {"type": "session_end", "session_id": session_id, "lot_id": lot_id,
                 "driver_id": driver_id, "duration_hours": round(dur, 2),
                 "amount": amount, "entry_price": entry_price,
                 "current_rate": cr, "timestamp": end_time.isoformat()},
                "payment",
                {"type": "payment", "session_id": session_id, "lot_id": lot_id,
                 "driver_id": driver_id, "action": "session_fee",
                 "amount": amount, "entry_price": entry_price, "final_price": cr})
            self._slot_op(lot_id, slot, "available")
            self.actuator.actuate(lot_id, current_occupancy, cr, 0.0)
            if lot_id not in self.dt.zones:
                self.dt.add_zone(lot_id, total_slots)
            else:
                self.dt.zones[lot_id]["occupancy"] = current_occupancy
                self.dt.zones[lot_id]["price"] = cr
            self.dt.tick({lot_id: 0.0})
            congestion = ("critical" if current_occupancy >= 0.85
                          else "high" if current_occupancy >= 0.65
                          else "moderate" if current_occupancy >= 0.40
                          else "normal")
            share_count = sum(
                1 for info in slot_resident_mapping.get_resident_slots(lot_id)
                if info.is_shared
            )
            self.dt.zones[lot_id]["n_share_listed"] = share_count
            return {
                "session_id": session_id, "lot_id": lot_id, "driver_id": driver_id,
                "duration_hours": float(round(dur, 2)),
                "entry_price": float(round(entry_price, 2)),
                "current_rate": float(round(cr, 2)),
                "amount_charged": float(amount),
                "blockchain_ref": cid, "end_time": end_time.isoformat(),
                "layers_activated": ["blockchain", "rl", "digital_twin", "actuator"],
            }

    def process_payment(self, session_id, driver_id, amount, lot_id):
        with self._lock:
            txh = hashlib.sha256(os.urandom(32)).hexdigest()[:16]
            ts = datetime.now(timezone.utc).isoformat()
            cid = self._pin_tx(
                {"type": "payment_confirmation", "session_id": session_id,
                 "driver_id": driver_id, "amount": amount, "lot_id": lot_id,
                 "tx_hash": txh, "timestamp": ts},
                "payment_confirmation",
                {"type": "payment_confirmation", "session_id": session_id,
                 "driver_id": driver_id, "lot_id": lot_id,
                 "action": "session_fee", "amount": amount, "tx_hash": txh})
            try:
                cr = self.revenue_contract.execute({
                    "price": amount, "driver_id": driver_id, "lot_id": lot_id})
                self.ledger.add_transaction({
                    "type": "revenue_share", "session_id": session_id,
                    "lot_id": lot_id, "driver_id": driver_id,
                    "action": "revenue_share", "amount": amount,
                    "distributions": cr["distributions"]})
            except Exception as e:
                logger.error("event=revshare.failed sess=%s amt=%.2f err=%s",
                             session_id, amount, e, exc_info=True)
            return {
                "session_id": session_id, "tx_hash": txh, "amount": amount,
                "blockchain_ref": cid, "ledger_blocks": len(self.ledger.chain),
            }

    def run_digital_twin_scenario(
        self, scenario_type="zone_closure", zone_id="zone_0"):
        # P6 / principle 8: this is a READ-ONLY what-if projection. It reads a
        # base state, evaluates deterministic scenarios, and persists each as a
        # TwinScenarioRun RECOMMENDATION. It never mutates production occupancy,
        # pricing, actuators, or the simulator state.
        base_state = self.dt.get_zone_state(zone_id)
        if base_state is None:
            return {"scenario": scenario_type, "zone_id": zone_id, "result": None,
                    "all_scenarios": [], "comparisons": [], "fallback": True,
                    "message": f"Zone {zone_id} not found in digital twin"}
        results = self.scenario_engine.run_all(base_state)
        self._persist_scenario_runs(zone_id, results)
        return {
            "scenario": scenario_type, "zone_id": zone_id,
            "result": next((r for r in results if r["scenario"] == scenario_type), None),
            "all_scenarios": results, "comparisons": self.scenario_engine.compare(base_state),
        }

    def _persist_scenario_runs(self, lot_id: str, results: list) -> None:
        """Persist scenario projections as recommendations (never actuate)."""
        try:
            from src.digital_twin.service import TwinService
            svc = TwinService()
            for r in results:
                res = r.get("result", {}) or {}
                svc.persist_scenario_run(
                    lot_id=str(lot_id),
                    scenario_type=r.get("scenario", "unknown"),
                    kind=r.get("kind", "deterministic"),
                    params={"description": r.get("description", "")},
                    predicted_occupancy_rate=res.get("occupancy_rate"),
                    predicted_price=res.get("price"),
                    assumptions="; ".join(r.get("assumptions", []) or []),
                    uncertainty_note=r.get("uncertainty", ""),
                    safety_note=r.get("safety", ""),
                )
        except Exception as e:  # persistence must never break the projection
            logger.warning("scenario run persistence failed: %s", e)

    def add_ledger_transaction(self, tx: dict) -> int:
        with self._lock:
            return self.ledger.add_transaction(tx)

    def mine_ledger(self) -> dict:
        with self._lock:
            block = self.ledger.mine_pending()
            self.ledger.save_to_file(self.bc_path)
            return {"block_index": block.index, "hash": block.hash,
                    "transactions": len(block.transactions), "nonce": block.nonce,
                    "timestamp": block.timestamp}

    def flush_ledger(self) -> bool:
        try:
            if self.ledger.pending_transactions:
                self.mine_ledger()
            return True
        except Exception:
            logger.exception("event=ledger.flush.failed")
            try:
                self.ledger = BlockchainLedger.load_from_file(self.bc_path)
            except Exception:
                logger.exception("event=ledger.flush.reload.failed")
            return False

    def simulate_ingest(self, db_session, lot) -> dict:
        latest = (
            db_session.query(OccupancyRecord)
            .filter(OccupancyRecord.lot_id == lot.lot_id)
            .order_by(OccupancyRecord.timestamp.desc()).first())
        drift = np.random.normal(0, 0.02)
        latest_occ = latest.occupancy_rate if (latest and latest.occupancy_rate is not None) else 0.3
        new_occ = max(0.0, min(1.0, latest_occ + (drift if latest else 0)))
        base = float(latest.price) if (latest and latest.price is not None) else float(lot.base_price)
        np_, _ = self._get_rl_price(new_occ, base, float(lot.price_cap))
        return {"lot_id": lot.lot_id, "occupied_slots": int(new_occ * lot.total_slots),
                "total_slots": lot.total_slots, "occupancy_rate": round(new_occ, 4),
                "pe_net_flux": 0.0, "price": round(np_, 2)}

    def status(self) -> dict:
        self.pricing.ensure()
        with self._lock:
            return {
                "ml_models": self.predictor.summary,
                "rl_agent": self.pricing.agent_available,
                "blockchain": {"chain_length": len(self.ledger.chain),
                               "pending_tx": len(self.ledger.pending_transactions)},
                "digital_twin": self.dt.summary(),
                "actuator": self.actuator.summary(),
            }


pipeline = PipelineOrchestrator()
