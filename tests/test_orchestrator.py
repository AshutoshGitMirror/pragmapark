import os
import tempfile
import joblib
import numpy as np
from src.pipeline.orchestrator import PipelineOrchestrator
from src.constants import DEFAULT_OCCUPANCY, DEFAULT_CAPACITY


class TestPipelineOrchestrator:
    def test_constructor(self):
        p = PipelineOrchestrator()
        assert p.predictor is not None
        assert p.pricing is not None
        assert p.ledger is not None
        assert len(p.ledger.chain) >= 1

    def test_status(self):
        p = PipelineOrchestrator()
        s = p.status()
        assert "ml_models" in s
        assert "rl_agent" in s
        assert "blockchain" in s
        assert "digital_twin" in s
        assert "actuator" in s

    def test_driver_search_lots_empty(self):
        p = PipelineOrchestrator()
        results = p.driver_search_lots([])
        assert results == []

    def test_driver_search_lots_single(self):
        p = PipelineOrchestrator()
        lots = [{"lot_id": "lot_1", "name": "Test", "total_slots": 100, "current_price": 10.0, "price_cap": 50.0}]
        results = p.driver_search_lots(lots)
        assert len(results) == 1
        assert results[0]["lot_id"] == "lot_1"
        assert "predicted_occupancy" in results[0]
        assert "dynamic_price" in results[0]
        assert "available_spots" in results[0]

    def test_driver_search_lots_sorted_by_available(self):
        p = PipelineOrchestrator()
        lots = [
            {"lot_id": "full", "total_slots": 100, "current_occupancy": 0.9, "current_price": 10.0, "price_cap": 50.0},
            {"lot_id": "empty", "total_slots": 100, "current_occupancy": 0.1, "current_price": 10.0, "price_cap": 50.0},
        ]
        results = p.driver_search_lots(lots)
        assert results[0]["lot_id"] == "empty"

    def test_start_session_returns_dict(self):
        p = PipelineOrchestrator()
        result = p.start_session("lot_1", "driver_1", slot=1, total_slots=100, base_price=10.0, price_cap=50.0)
        assert result["session_id"] is not None
        assert result["lot_id"] == "lot_1"
        assert result["driver_id"] == "driver_1"
        assert "price_at_entry" in result
        assert "blockchain_ref" in result
        assert "layers_activated" in result

    def test_start_session_with_features(self):
        import pandas as pd
        p = PipelineOrchestrator()
        features = pd.Series({
            "occupancy_rate": 0.5, "occupied_slots": 50, "total_slots": 100,
            "occ_lag_15m": 0.4, "occ_lag_1h": 0.3, "net_flux": 0.0,
        })
        result = p.start_session("lot_1", "driver_1", slot=1, total_slots=100,
                                  base_price=10.0, price_cap=50.0, features=features)
        assert result["session_id"] is not None
        assert "predicted_occupancy" in result

    def test_end_session(self):
        p = PipelineOrchestrator()
        import datetime
        start = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)).isoformat()
        result = p.end_session("sess_1", "lot_1", "driver_1", start, 0.5, 10.0, 100, 50.0, slot=1)
        assert result["session_id"] == "sess_1"
        assert result["duration_hours"] >= 1.0
        assert "amount_charged" in result
        assert "blockchain_ref" in result

    def test_end_session_with_bad_start_time(self):
        p = PipelineOrchestrator()
        result = p.end_session("sess_2", "lot_1", "driver_1", "bad_time", 0.5, 10.0, 100, 50.0, slot=1)
        assert result["duration_hours"] == 1.0

    def test_process_payment(self):
        p = PipelineOrchestrator()
        result = p.process_payment("sess_1", "driver_1", 15.50, "lot_1")
        assert result["session_id"] == "sess_1"
        assert "tx_hash" in result
        assert result["amount"] == 15.50
        assert "ledger_blocks" in result

    def test_add_ledger_transaction(self):
        p = PipelineOrchestrator()
        idx = p.add_ledger_transaction({"type": "test", "data": "hello"})
        assert isinstance(idx, int)

    def test_mine_ledger(self):
        p = PipelineOrchestrator()
        p.add_ledger_transaction({"type": "test"})
        block = p.mine_ledger()
        assert "block_index" in block
        assert "hash" in block
        assert block["transactions"] >= 1

    def test_flush_ledger_returns_true_when_empty(self):
        p = PipelineOrchestrator()
        assert p.flush_ledger() is True

    def test_run_digital_twin_scenario(self):
        p = PipelineOrchestrator()
        result = p.run_digital_twin_scenario("zone_closure", "zone_0")
        assert result["scenario"] == "zone_closure"
        assert result["zone_id"] == "zone_0"
        assert "all_scenarios" in result

    def test_simulate_ingest(self, monkeypatch):
        from src.api.database import ParkingLot, get_session
        db = get_session()
        try:
            lot = ParkingLot(lot_id="sim_lot", name="Sim", total_slots=100, base_price=10.0, price_cap=50.0)
            db.add(lot)
            db.commit()
            p = PipelineOrchestrator()
            result = p.simulate_ingest(db, lot)
            assert result["lot_id"] == "sim_lot"
            assert "occupancy_rate" in result
            assert "price" in result
        finally:
            db.close()
