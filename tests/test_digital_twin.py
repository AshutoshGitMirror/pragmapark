import pytest
import sys
import os
import logging
import numpy as np

sys.path.append(os.getcwd())

from src.digital_twin import DigitalTwinSimulator, ScenarioEngine, Generator
from src.digital_twin.scenario import CounterfactualScenario


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
        assert len(engine.scenarios) == 5

    def test_scenario_zone_closure(self):
        engine = ScenarioEngine()
        engine.register_defaults()
        base = {"zone_id": "z0", "occupancy_rate": 0.5, "price": 10.0,
                "total_slots": 500, "available_slots": 250, "congestion_level": "normal"}
        results = engine.run_all(base)
        closure = [r for r in results if r["scenario"] == "zone_closure"][0]
        assert closure["result"]["congestion_level"] == "critical"

    def test_scenario_comparison(self):
        engine = ScenarioEngine()
        engine.register_defaults()
        base = {"zone_id": "z0", "occupancy_rate": 0.5, "price": 10.0,
                "total_slots": 500, "available_slots": 250, "congestion_level": "normal"}
        engine.run_all(base)
        comps = engine.compare(base)
        assert len(comps) == 5
        assert all("occupancy_delta" in c for c in comps)

    def test_generative_simulator_synthesis(self):
        gen = Generator(latent_dim=8)
        result = gen.synthesize_scenario(0.5, 10.0)
        assert len(result) == 3
        assert 0 <= result[0] <= 1
        assert 5 <= result[1] <= 50

    def test_scenario_vae_informed(self):
        gen = Generator(latent_dim=8)
        engine = ScenarioEngine(generator=gen)
        engine.register_defaults()
        base = {"zone_id": "z0", "occupancy_rate": 0.5, "price": 10.0,
                "total_slots": 500, "available_slots": 250, "congestion_level": "normal"}
        results = engine.run_all(base)
        assert len(results) == 5
        for r in results:
            assert "occupancy_rate" in r["result"]
            assert "price" in r["result"]

    def test_online_update_trains_vae(self):
        """Verify VAE weights shift after online_update accumulates enough sessions."""
        gen = Generator(latent_dim=8)
        initial_W = gen.W.copy()
        assert gen.trained is False

        # Feed 12 synthetic session outcomes (batch_size=10)
        for i in range(12):
            occ = 0.3 + (i % 5) * 0.1    # varied occupancy
            price = 8.0 + i * 2.0         # varied price
            dur = 1.0 + i * 0.5           # varied duration
            cong = "normal" if i < 4 else "moderate" if i < 8 else "high"
            result = gen.online_update(occ, price, dur, cong)
            if result["trained"]:
                assert result["loss"] > 0
                assert result["total_steps"] >= 1

        # Buffer auto-empties after training; should now have 2 samples buffered
        assert len(gen._online_buffer) == 2
        assert gen.trained is True

        # Verify decoder weights changed from training
        assert not np.allclose(gen.W, initial_W, atol=1e-8), \
            "VAE decoder weights did not shift after online_update"
        logger = logging.getLogger(__name__)
        logger.info("VAE online_update: W diff=%.6f (trained=%s)",
                    float(np.abs(gen.W - initial_W).mean()), gen.trained)
