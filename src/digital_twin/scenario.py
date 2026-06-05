import numpy as np
import inspect
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional
from src.constants import DEFAULT_OCCUPANCY, DEFAULT_CAPACITY
from src.digital_twin.generator import Generator

CLOSURE_PRICE_MULTIPLIER = 1.5
CLOSURE_OCCUPANCY = 1.0
SURGE_OCCUPANCY_DELTA = -0.15
EXPANSION_CAPACITY_MULTIPLIER = 1.2
EXPANSION_OCCUPANCY_FACTOR = 0.83
WEATHER_OCCUPANCY_DELTA = -0.3
HOLIDAY_OCCUPANCY_MULTIPLIER = 1.25
HOLIDAY_CONGESTION_THRESHOLD = 0.8


@dataclass
class CounterfactualScenario:
    name: str
    description: str
    apply_fn: Callable
    impacts: Dict = field(default_factory=dict)

    def run(self, base_state: dict, v_state: dict) -> dict:
        # Backward-compatible with single-argument scenario functions
        sig = inspect.signature(self.apply_fn)
        if len(sig.parameters) >= 2:
            modified = self.apply_fn(base_state.copy(), v_state)
        else:
            modified = self.apply_fn(base_state.copy())
        self.impacts = self._compute_impacts(base_state, modified)
        return modified

    def _compute_impacts(self, base: dict, modified: dict) -> dict:
        impacts = {}
        for key in base:
            if isinstance(base[key], (int, float)):
                impacts[f"{key}_delta"] = modified.get(key, 0) - base[key]
                if base[key] != 0:
                    impacts[f"{key}_pct"] = (
                        (modified.get(key, 0) - base[key]) / abs(base[key]) * 100
                    )
        return impacts


class ScenarioEngine:
    def __init__(self, generator: Optional[Generator] = None):
        self.generator = generator if generator is not None else Generator(latent_dim=8)
        self.scenarios: List[CounterfactualScenario] = []
        self.results: List[Dict] = []

    def register_defaults(self):
        # 1. Zone Closure — force closure, VAE guides price surge
        def apply_zone_closure(s: dict, v: dict) -> dict:
            price = float(np.clip(
                max(s.get("price", 10.0) * CLOSURE_PRICE_MULTIPLIER, v["price"] * 1.2),
                5.0, 200.0))
            return {
                **s, "occupancy_rate": CLOSURE_OCCUPANCY,
                "available_slots": 0, "congestion_level": "critical",
                "price": price,
            }

        # 2. Price Surge — surge price, VAE-informed elasticity drop
        def apply_price_surge(s: dict, v: dict) -> dict:
            price = float(np.clip(
                max(s.get("price", 10.0) * CLOSURE_PRICE_MULTIPLIER, v["price"]),
                5.0, 200.0))
            occ_diff = abs(v["occupancy_rate"] - s.get("occupancy_rate", DEFAULT_OCCUPANCY))
            occupancy = float(np.clip(
                s.get("occupancy_rate", DEFAULT_OCCUPANCY) - occ_diff - 0.05,
                0.0, 1.0))
            return {
                **s, "price": price, "occupancy_rate": occupancy,
                "available_slots": int(s.get("total_slots", DEFAULT_CAPACITY) * (1.0 - occupancy)),
            }

        # 3. Capacity Expansion — VAE variance blended into occupancy drop
        def apply_capacity_expansion(s: dict, v: dict) -> dict:
            total_slots = int(s.get("total_slots", DEFAULT_CAPACITY) * EXPANSION_CAPACITY_MULTIPLIER)
            occ_diff = v["occupancy_rate"] - s.get("occupancy_rate", DEFAULT_OCCUPANCY)
            occupancy = float(np.clip(
                s.get("occupancy_rate", DEFAULT_OCCUPANCY) * EXPANSION_OCCUPANCY_FACTOR + occ_diff * 0.1,
                0.0, 1.0))
            return {
                **s, "total_slots": total_slots, "occupancy_rate": occupancy,
                "available_slots": int(total_slots * (1.0 - occupancy)),
            }

        # 4. Weather Disruption — VAE occupancy fluctuations guide drop
        def apply_weather_disruption(s: dict, v: dict) -> dict:
            occ_diff = abs(v["occupancy_rate"] - s.get("occupancy_rate", DEFAULT_OCCUPANCY))
            occupancy = float(np.clip(
                s.get("occupancy_rate", DEFAULT_OCCUPANCY) - occ_diff + WEATHER_OCCUPANCY_DELTA,
                0.0, 1.0))
            return {
                **s, "occupancy_rate": occupancy,
                "available_slots": int(s.get("total_slots", DEFAULT_CAPACITY) * (1.0 - occupancy)),
                "congestion_level": "normal" if occupancy < 0.5 else "moderate",
            }

        # 5. Holiday Spike — VAE fluctuations blended with demand surge
        def apply_holiday_spike(s: dict, v: dict) -> dict:
            occ_diff = abs(v["occupancy_rate"] - s.get("occupancy_rate", DEFAULT_OCCUPANCY))
            holiday_bump = (HOLIDAY_OCCUPANCY_MULTIPLIER - 1.0) * s.get("occupancy_rate", DEFAULT_OCCUPANCY)
            occupancy = float(np.clip(
                s.get("occupancy_rate", DEFAULT_OCCUPANCY) + occ_diff + holiday_bump,
                0.0, 1.0))
            price = float(np.clip(
                s.get("price", 10.0) * (1.1 + abs(v["price"] - s.get("price", 10.0)) / 100.0),
                5.0, 200.0))
            congestion = "high" if occupancy > HOLIDAY_CONGESTION_THRESHOLD else "moderate"
            return {
                **s, "price": price, "occupancy_rate": occupancy,
                "available_slots": int(s.get("total_slots", DEFAULT_CAPACITY) * (1.0 - occupancy)),
                "congestion_level": congestion,
            }

        self.scenarios = [
            CounterfactualScenario("zone_closure", "Simulate sudden closure of a parking zone", apply_zone_closure),
            CounterfactualScenario("price_surge", "Apply price surge and measure demand elasticity", apply_price_surge),
            CounterfactualScenario("capacity_expansion", "Add 20% more parking spots to a zone", apply_capacity_expansion),
            CounterfactualScenario("weather_disruption", "Severe weather reduces demand", apply_weather_disruption),
            CounterfactualScenario("holiday_spike", "Holiday period increases demand", apply_holiday_spike),
        ]

    def add_scenario(self, scenario: CounterfactualScenario):
        self.scenarios.append(scenario)

    def run_all(self, base_state: dict) -> List[Dict]:
        self.results = []
        base_occ = base_state.get("occupancy_rate", DEFAULT_OCCUPANCY)
        base_price_val = base_state.get("price", 10.0)
        for idx, scenario in enumerate(self.scenarios):
            # Each scenario gets its own CVAE-conditional generative state
            v_occ, v_price, v_congestion = self.generator.synthesize_scenario(
                base_occ, base_price_val, scenario_idx=idx)
            v_state = {"occupancy_rate": v_occ, "price": v_price, "congestion": v_congestion}
            modified = scenario.run(base_state, v_state)
            self.results.append({
                "scenario": scenario.name,
                "description": scenario.description,
                "impacts": scenario.impacts,
                "result": modified,
            })
        return self.results

    def compare(self, base_state: dict) -> List[Dict]:
        comparisons = []
        for result in self.results:
            impacts = result["impacts"]
            comp = {
                "scenario": result["scenario"],
                "occupancy_delta": f"{impacts.get('occupancy_rate_delta', 0):+.2%}",
                "price_delta": f"${impacts.get('price_delta', 0):+.2f}",
                "congestion": result["result"].get("congestion_level", "unknown"),
            }
            comparisons.append(comp)
        return comparisons
