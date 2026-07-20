import sys
import os
import logging
import numpy as np

sys.path.append(os.getcwd())

from src.digital_twin import (  # noqa: E402
    DigitalTwinSimulator,
    ScenarioEngine,
    STIDPredictor,
)
from fastapi.testclient import TestClient  # noqa: E402

logger = logging.getLogger(__name__)


class TestDigitalTwin:
    def test_simulator_initialization(self):
        sim = DigitalTwinSimulator()
        sim.add_zone("zone_0", 500)
        sim.add_zone("zone_1", 300)
        assert len(sim.zones) == 2
        assert sim.zones["zone_0"]["capacity"] == 500

    def test_simulator_tick(self):
        sim = DigitalTwinSimulator()
        sim.add_zone("zone_0", 500)
        states = sim.tick({"zone_0": 0.1})
        assert len(states) == 1
        assert 0 <= states[0].occupancy_rate <= 1
        assert 5 <= states[0].price <= 50

    def test_simulator_summary(self):
        sim = DigitalTwinSimulator()
        sim.add_zone("zone_0", 500)
        sim.tick({"zone_0": 0.0})
        summary = sim.summary()
        assert summary["zones"] == 1
        assert "mean_occupancy" in summary

    def test_scenario_engine_defaults(self):
        engine = ScenarioEngine()
        engine.register_defaults()
        assert len(engine.scenarios) == 6

    def test_scenario_zone_closure(self):
        engine = ScenarioEngine()
        engine.register_defaults()
        base = {
            "zone_id": "z0",
            "occupancy_rate": 0.5,
            "price": 10.0,
            "total_slots": 500,
            "available_slots": 250,
            "congestion_level": "normal",
        }
        results = engine.run_all(base)
        closure = [r for r in results if r["scenario"] == "zone_closure"][0]
        assert closure["result"]["congestion_level"] == "critical"

    def test_scenario_comparison(self):
        engine = ScenarioEngine()
        engine.register_defaults()
        base = {
            "zone_id": "z0",
            "occupancy_rate": 0.5,
            "price": 10.0,
            "total_slots": 500,
            "available_slots": 250,
            "congestion_level": "normal",
        }
        engine.run_all(base)
        comps = engine.compare(base)
        assert len(comps) == 6
        assert all("occupancy_delta" in c for c in comps)

    def test_scenarios_are_deterministic_not_learned(self):
        """P4/P5: scenarios must be classified 'deterministic', never
        'learned counterfactual', and must not require a generative model."""
        engine = ScenarioEngine()
        engine.register_defaults()
        assert engine.generator is None
        for sc in engine.scenarios:
            assert sc.kind == "deterministic"
            # Honest scenarios must record their assumptions + uncertainty.
            assert isinstance(sc.assumptions, list) and len(sc.assumptions) > 0
            assert sc.uncertainty
            assert "does not mutate" in sc.safety.lower() or "NOT" in sc.safety

    def test_scenario_run_all_is_read_only(self):
        """P6/P8: run_all must not mutate the base_state dict passed in."""
        engine = ScenarioEngine()
        engine.register_defaults()
        base = {
            "zone_id": "z0",
            "occupancy_rate": 0.5,
            "price": 10.0,
            "total_slots": 500,
            "available_slots": 250,
            "congestion_level": "normal",
        }
        snapshot = dict(base)
        engine.run_all(base)
        assert base == snapshot, "run_all mutated the caller's base_state"

    def test_scenario_share_fraction_normalized_to_capacity(self):
        """P4: resident_share_adoption frees POLICY_REDISTRIBUTION_FRACTION of
        real total_slots, not a free-floating 15% of occupancy."""
        from src.digital_twin.scenario import POLICY_REDISTRIBUTION_FRACTION

        engine = ScenarioEngine()
        engine.register_defaults()
        total = 400
        base = {
            "zone_id": "z0",
            "occupancy_rate": 0.5,
            "price": 10.0,
            "total_slots": total,
            "available_slots": 200,
            "congestion_level": "normal",
        }
        results = engine.run_all(base)
        share = [r for r in results if r["scenario"] == "resident_share_adoption"][0]
        expected_freed = int(round(total * POLICY_REDISTRIBUTION_FRACTION))
        assert share["result"]["freed_slots"] == expected_freed
        # occupancy is recomputed from freed slots / capacity, in [0,1]
        assert 0.0 <= share["result"]["occupancy_rate"] <= 1.0

    def test_scenario_reproducibility(self):
        """P7 reproducibility: identical base_state yields identical results."""
        engine = ScenarioEngine()
        engine.register_defaults()
        base = {
            "zone_id": "z0",
            "occupancy_rate": 0.5,
            "price": 10.0,
            "total_slots": 500,
            "available_slots": 250,
            "congestion_level": "normal",
        }
        r1 = engine.run_all(base)
        r2 = engine.run_all(base)
        for a, b in zip(r1, r2):
            assert a["result"] == b["result"]

    def test_stid_predictor(self):
        """STIDPredictor initializes, predicts, and trains ONLY on real obs.

        The model is now trained via ``train_on_real_observation`` (no
        synthetic/self-training path). Training on a real-valued target in
        [0, 1] should decrease loss.
        """
        np.random.seed(42)
        stid = STIDPredictor(num_zones=4, spatial_dim=4, temporal_dim=4)
        stid.set_zone_index(["L1", "L2", "L3", "L4"])

        # Initial prediction
        pred_before = stid.predict(zone_idx=0, hour=12, day=1, history_occ=0.5)
        assert 0.0 <= pred_before <= 1.0

        # Train only on a real observed occupancy of 0.8 (must be in [0, 1]).
        initial_loss = stid.train_on_real_observation(
            lot_id="L1", hour=12, day=1, history_occ=0.5, observed_occ=0.8, lr=0.1
        )

        loss = initial_loss
        for _ in range(50):
            loss = stid.train_on_real_observation(
                lot_id="L1", hour=12, day=1, history_occ=0.5, observed_occ=0.8, lr=0.1
            )

        pred_after = stid.predict(zone_idx=0, hour=12, day=1, history_occ=0.5)

        # Prediction should move closer to the target (0.8)
        assert abs(pred_after - 0.8) < abs(pred_before - 0.8)
        assert loss < initial_loss
        # The model must only ever be trained on real observations.
        assert stid.trained_real_steps == 51

    def test_simulator_db_bootstrapping(self):
        """Verify DigitalTwinSimulator bootstraps zones from DB."""
        from src.api.database import (
            get_db_cm,
            ParkingLot,
            OccupancyRecord,
            get_engine,
            Base,
        )

        # Ensure tables are created for testing database
        engine = get_engine()
        Base.metadata.create_all(bind=engine)

        with get_db_cm() as db:
            # Clean up first to avoid key conflicts
            db.query(OccupancyRecord).filter(
                OccupancyRecord.lot_id == "bootstrap_lot_1"
            ).delete()
            db.query(ParkingLot).filter(
                ParkingLot.lot_id == "bootstrap_lot_1"
            ).delete()
            db.commit()

            # Seed a test lot and occupancy record
            lot = ParkingLot(
                lot_id="bootstrap_lot_1",
                name="Bootstrap Lot 1",
                total_slots=250,
                base_price=12.5,
            )
            db.add(lot)
            db.flush()
            db.add(
                OccupancyRecord(
                    lot_id="bootstrap_lot_1",
                    occupied_slots=100,
                    total_slots=250,
                    occupancy_rate=0.4,
                    price=14.0,
                )
            )
            db.commit()

        # Instantiate a fresh simulator with no zones
        sim = DigitalTwinSimulator()
        assert "bootstrap_lot_1" not in sim.zones

        # Calling get_zone_state should trigger bootstrap_from_db
        state = sim.get_zone_state("bootstrap_lot_1")
        assert state is not None
        assert state["zone_id"] == "bootstrap_lot_1"
        assert state["capacity"] == 250
        assert state["occupancy_rate"] == 0.4
        assert state["price"] == 14.0
        assert state["available_slots"] == 150

        # Clean up
        with get_db_cm() as db:
            db.query(OccupancyRecord).filter(
                OccupancyRecord.lot_id == "bootstrap_lot_1"
            ).delete()
            db.query(ParkingLot).filter(
                ParkingLot.lot_id == "bootstrap_lot_1"
            ).delete()
            db.commit()

    def test_dt_get_state_endpoint(self):
        """P5: legacy digital-twin state endpoint reports
        generator_runtime=False and does NOT expose a trained-generator flag.
        The CVAE-WGAN is offline-only and never instantiated at runtime."""
        from fastapi import FastAPI
        from src.api.routes.digital_twin import router as dt_router
        from src.pipeline.orchestrator import pipeline

        app = FastAPI()
        app.include_router(dt_router)
        client = TestClient(app)

        if "test_dt_state" not in pipeline.dt.zones:
            pipeline.dt.add_zone("test_dt_state", 200)

        response = client.get("/api/v1/digital-twin/state")
        assert response.status_code == 200
        data = response.json()
        assert "zones" in data
        assert "test_dt_state" in data["zones"]
        zone = data["zones"]["test_dt_state"]
        assert "n_share_listed" in zone
        assert zone["n_share_listed"] == 0
        assert "current_time" in data
        assert "history_length" in data
        # Runtime must NOT run a CVAE-WGAN.
        assert data.get("generator_runtime") is False
        # No trained-generator claim is surfaced (honest about offline status).
        assert "generator_trained" not in data

    def test_legacy_generate_endpoint_is_deterministic_no_gan(self):
        """P5: /generate is a deterministic deprecation endpoint that does NOT
        call a trained GAN. It returns a deterministic congestion bucket
        derived only from the request inputs, never a generative sample."""
        from fastapi import FastAPI
        from src.api.routes.digital_twin import router as dt_router
        from src.api.auth import get_current_user

        app = FastAPI()
        app.include_router(dt_router)
        app.dependency_overrides[get_current_user] = lambda: {
            "role": "admin",
            "user_id": 1,
        }
        client = TestClient(app)

        # Deterministic: same inputs -> identical outputs (no sampling).
        payload = {"base_occupancy": 0.5, "base_price": 10.0}
        r1 = client.post("/api/v1/digital-twin/generate", json=payload)
        r2 = client.post("/api/v1/digital-twin/generate", json=payload)
        assert r1.status_code == 200
        assert r2.status_code == 200
        d1, d2 = r1.json(), r2.json()
        assert d1 == d2, "generate endpoint is not deterministic"
        # Congestion bucket is a fixed function of occupancy (not a GAN sample).
        assert d1["congestion_score"] == 0.33  # 0.40 <= 0.5 < 0.65 bucket
        assert d1["synthetic_occupancy"] == 0.5
        assert d1["shared_occupancy"] == 0.0

        app.dependency_overrides.clear()
