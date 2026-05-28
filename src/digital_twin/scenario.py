from dataclasses import dataclass, field
from typing import Callable, Dict, List
from src.constants import DEFAULT_OCCUPANCY, DEFAULT_CAPACITY

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

    def run(self, base_state: dict) -> dict:
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
    def __init__(self):
        self.scenarios: List[CounterfactualScenario] = []
        self.results: List[Dict] = []

    def register_defaults(self):
        self.scenarios.append(CounterfactualScenario(
            name="zone_closure",
            description="Simulate sudden closure of a parking zone",
            apply_fn=lambda s: {**s, "occupancy_rate": CLOSURE_OCCUPANCY,
                                "available_slots": 0,
                                "congestion_level": "critical",
                                "price": s.get("price", 10) * CLOSURE_PRICE_MULTIPLIER},
        ))
        self.scenarios.append(CounterfactualScenario(
            name="price_surge",
            description="Apply 50% price surge and measure demand elasticity",
            apply_fn=lambda s: {**s, "price": s.get("price", 10) * CLOSURE_PRICE_MULTIPLIER,
                                "occupancy_rate": max(0, s.get("occupancy_rate", DEFAULT_OCCUPANCY) + SURGE_OCCUPANCY_DELTA)},
        ))
        self.scenarios.append(CounterfactualScenario(
            name="capacity_expansion",
            description="Add 20% more parking spots to a zone",
            apply_fn=lambda s: {**s, "total_slots": int(s.get("total_slots", DEFAULT_CAPACITY) * EXPANSION_CAPACITY_MULTIPLIER),
                                "occupancy_rate": s.get("occupancy_rate", DEFAULT_OCCUPANCY) * EXPANSION_OCCUPANCY_FACTOR},
        ))
        self.scenarios.append(CounterfactualScenario(
            name="weather_disruption",
            description="Severe weather reduces demand by 30%",
            apply_fn=lambda s: {**s, "occupancy_rate": max(0, s.get("occupancy_rate", DEFAULT_OCCUPANCY) + WEATHER_OCCUPANCY_DELTA),
                                "congestion_level": "normal"},
        ))
        self.scenarios.append(CounterfactualScenario(
            name="holiday_spike",
            description="Holiday period increases demand by 25%",
            apply_fn=lambda s: {**s, "occupancy_rate": min(1.0, s.get("occupancy_rate", DEFAULT_OCCUPANCY) * HOLIDAY_OCCUPANCY_MULTIPLIER),
                                "congestion_level": "high" if s.get("occupancy_rate", DEFAULT_OCCUPANCY) * HOLIDAY_OCCUPANCY_MULTIPLIER > HOLIDAY_CONGESTION_THRESHOLD else "moderate"},
        ))

    def add_scenario(self, scenario: CounterfactualScenario):
        self.scenarios.append(scenario)

    def run_all(self, base_state: dict) -> List[Dict]:
        self.results = []
        for scenario in self.scenarios:
            modified = scenario.run(base_state)
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
