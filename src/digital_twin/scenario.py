"""Honest scenario engine for the digital twin.

IMPORTANT (principles 3, 4, 8 of the digital-twin remediation):
- These scenarios are DETERMINISTIC, RULE-BASED what-if projections. They are
  explicitly NOT "learned counterfactuals" and NOT causal estimates. They have
  no intervention/outcome training data and are labelled ``deterministic``.
- They never read or mutate production state (principle 8: scenarios never
  auto-actuate). They receive a base-state dict and return a projection dict.
- The CVAE-WGAN generator is NOT used here (see P5). No synthetic data is
  treated as evidence.

Each scenario records its assumptions, uncertainty, and a safety note so the
caller (twin UI / operator) sees exactly what is a policy assumption vs a
measured effect.
"""
import numpy as np
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from src.constants import DEFAULT_OCCUPANCY, DEFAULT_CAPACITY
from src.constants import RESIDENT_SHARE_ADOPTION_RATES

# Named policy constants (principle 4: no magic 15% rule left unnamed).
# Fractional occupancy-rate reduction assumed under a resident-share adoption
# scenario, taken from the published adoption-rate ladder in constants.py.
POLICY_REDISTRIBUTION_FRACTION = RESIDENT_SHARE_ADOPTION_RATES[2]  # 0.15

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
    """A deterministic what-if projection.

    ``kind`` is one of: ``deterministic`` (pure rule), ``calibrated`` (rule
    with an uncertainty band from observed data), ``learned`` (trained on
    intervention/outcome data). The current engine only provides
    ``deterministic`` scenarios; ``learned`` is intentionally unsupported
    until labelled intervention/outcome data exists (principle 4).
    """

    name: str
    description: str
    apply_fn: Callable
    kind: str = "deterministic"
    impacts: Dict = field(default_factory=dict)
    occupancy_shift: int = 0
    price_adjust: float = 0.0
    assumptions: List[str] = field(default_factory=list)
    uncertainty: str = ""
    safety: str = (
        "Projection only. Does NOT mutate production state; an operator "
        "or the RL controller must decide before any action is taken."
    )

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
                        (modified.get(key, 0) - base[key])
                        / abs(base[key])
                        * 100
                    )
        return impacts


class ScenarioEngine:
    """Deterministic scenario engine. No generative model, no auto-actuation."""

    def __init__(self):
        self.scenarios: List[CounterfactualScenario] = []
        self.results: List[Dict] = []
        # P5: the engine is purely deterministic and never holds a generative
        # model. Kept as an explicit None to document the offline-only split
        # (the CVAE-WGAN lives in generator.py and is never injected here).
        self.generator = None

    def register_defaults(self):
        # 1. Zone Closure — hard closure: occupancy saturates, slots gone.
        def apply_zone_closure(s: dict) -> dict:
            return {
                **s,
                "occupancy_rate": CLOSURE_OCCUPANCY,
                "available_slots": 0,
                "congestion_level": "critical",
                "price": float(
                    np.clip(
                        s.get("price", 10.0) * CLOSURE_PRICE_MULTIPLIER,
                        5.0,
                        200.0,
                    )
                ),
            }

        # 2. Price Surge — demand elasticity assumption reduces occupancy.
        def apply_price_surge(s: dict) -> dict:
            occupancy = float(
                np.clip(
                    s.get("occupancy_rate", DEFAULT_OCCUPANCY)
                    + SURGE_OCCUPANCY_DELTA,
                    0.0,
                    1.0,
                )
            )
            return {
                **s,
                "price": float(
                    np.clip(
                        s.get("price", 10.0) * CLOSURE_PRICE_MULTIPLIER,
                        5.0,
                        200.0,
                    )
                ),
                "occupancy_rate": occupancy,
                "available_slots": int(
                    s.get("total_slots", DEFAULT_CAPACITY) * (1.0 - occupancy)
                ),
            }

        # 3. Capacity Expansion — more slots dilute occupancy per slot.
        def apply_capacity_expansion(s: dict) -> dict:
            total_slots = int(
                s.get("total_slots", DEFAULT_CAPACITY)
                * EXPANSION_CAPACITY_MULTIPLIER
            )
            occupancy = float(
                np.clip(
                    s.get("occupancy_rate", DEFAULT_OCCUPANCY)
                    * EXPANSION_OCCUPANCY_FACTOR,
                    0.0,
                    1.0,
                )
            )
            return {
                **s,
                "total_slots": total_slots,
                "occupancy_rate": occupancy,
                "available_slots": int(total_slots * (1.0 - occupancy)),
            }

        # 4. Weather Disruption — assumed demand drop.
        def apply_weather_disruption(s: dict) -> dict:
            occupancy = float(
                np.clip(
                    s.get("occupancy_rate", DEFAULT_OCCUPANCY)
                    + WEATHER_OCCUPANCY_DELTA,
                    0.0,
                    1.0,
                )
            )
            return {
                **s,
                "occupancy_rate": occupancy,
                "available_slots": int(
                    s.get("total_slots", DEFAULT_CAPACITY) * (1.0 - occupancy)
                ),
                "congestion_level": (
                    "normal" if occupancy < 0.5 else "moderate"
                ),
            }

        # 5. Holiday Spike — assumed demand increase.
        def apply_holiday_spike(s: dict) -> dict:
            base_occ = s.get("occupancy_rate", DEFAULT_OCCUPANCY)
            holiday_bump = (HOLIDAY_OCCUPANCY_MULTIPLIER - 1.0) * base_occ
            occupancy = float(np.clip(base_occ + holiday_bump, 0.0, 1.0))
            return {
                **s,
                "price": float(
                    np.clip(s.get("price", 10.0) * 1.1, 5.0, 200.0)
                ),
                "occupancy_rate": occupancy,
                "available_slots": int(
                    s.get("total_slots", DEFAULT_CAPACITY) * (1.0 - occupancy)
                ),
                "congestion_level": (
                    "high" if occupancy > HOLIDAY_CONGESTION_THRESHOLD else "moderate"
                ),
            }

        # 6. Resident Share Adoption — share listings free up slots.
        # Normalized to LOT CAPACITY (principle: share fraction of real slots,
        # not a free-floating 0.15 applied to occupancy). The freed-slot count
        # is POLICY_REDISTRIBUTION_FRACTION * total_slots.
        def _scenario_resident_share_adoption(s: dict) -> dict:
            total = s.get("total_slots", DEFAULT_CAPACITY)
            freed = int(round(total * POLICY_REDISTRIBUTION_FRACTION))
            occupied = int(round(s.get("occupancy_rate", DEFAULT_OCCUPANCY) * total))
            new_occupied = max(0, occupied - freed)
            occ = float(np.clip(new_occupied / total, 0.0, 1.0)) if total else 0.0
            return {
                **s,
                "occupancy_rate": occ,
                "available_slots": int(total - new_occupied),
                "freed_slots": freed,
                "congestion_level": "moderate" if occ > 0.6 else "normal",
            }

        self.scenarios = [
            CounterfactualScenario(
                "zone_closure",
                "Simulate sudden closure of a parking zone",
                apply_zone_closure,
                kind="deterministic",
                occupancy_shift=50,
                price_adjust=0.5,
                assumptions=[
                    "Closed zone cannot serve demand; occupancy saturates to 1.0.",
                    "Remaining demand spills to neighbouring zones (not modelled here).",
                ],
                uncertainty="No spillover modelled; absolute slot loss is exact, "
                "neighbourhood impact is unbounded.",
            ),
            CounterfactualScenario(
                "price_surge",
                "Apply price surge and measure assumed demand elasticity",
                apply_price_surge,
                kind="deterministic",
                occupancy_shift=-15,
                price_adjust=0.5,
                assumptions=[
                    f"Occupancy drops by a fixed {SURGE_OCCUPANCY_DELTA} "
                    "fraction under higher price (policy assumption, not estimated)."
                ],
                uncertainty="Elasticity is a fixed rule, not a fitted demand curve.",
            ),
            CounterfactualScenario(
                "capacity_expansion",
                "Add 20% more parking spots to a zone",
                apply_capacity_expansion,
                kind="deterministic",
                occupancy_shift=-17,
                price_adjust=0.0,
                assumptions=[
                    "Total slots scale by EXPANSION_CAPACITY_MULTIPLIER.",
                    "Occupancy per slot scales by EXPANSION_OCCUPANCY_FACTOR.",
                ],
                uncertainty="Assumes demand is unchanged; real occupancy depends "
                "on latent demand not captured here.",
            ),
            CounterfactualScenario(
                "weather_disruption",
                "Severe weather reduces demand (assumed)",
                apply_weather_disruption,
                kind="deterministic",
                occupancy_shift=-30,
                price_adjust=-0.1,
                assumptions=[
                    f"Occupancy drops by a fixed {WEATHER_OCCUPANCY_DELTA} fraction."
                ],
                uncertainty="Weather effect is a fixed rule; not conditioned on "
                "forecast or observed weather.",
            ),
            CounterfactualScenario(
                "holiday_spike",
                "Holiday period increases demand (assumed)",
                apply_holiday_spike,
                kind="deterministic",
                occupancy_shift=25,
                price_adjust=0.1,
                assumptions=[
                    f"Occupancy scales by HOLIDAY_OCCUPANCY_MULTIPLIER.",
                ],
                uncertainty="Holiday effect is a fixed rule; not holiday-specific.",
            ),
            CounterfactualScenario(
                "resident_share_adoption",
                "Gradual resident share listing adoption frees up slots",
                _scenario_resident_share_adoption,
                kind="deterministic",
                occupancy_shift=-10,
                price_adjust=-0.05,
                assumptions=[
                    f"Freed slots = POLICY_REDISTRIBUTION_FRACTION "
                    f"({POLICY_REDISTRIBUTION_FRACTION}) * total_slots.",
                    "Assumes shared slots are additional supply, not a shift "
                    "of existing occupancy.",
                ],
                uncertainty="Adoption fraction is a policy constant, not measured "
                "take-up; real freed capacity depends on actual listings.",
            ),
        ]

    def add_scenario(self, scenario: CounterfactualScenario):
        self.scenarios.append(scenario)

    def run_all(self, base_state: dict) -> List[Dict]:
        """Run every registered scenario as a read-only projection.

        Does NOT mutate ``base_state`` or any production state.
        """
        self.results = []
        for scenario in self.scenarios:
            modified = scenario.run(base_state)
            self.results.append(
                {
                    "scenario": scenario.name,
                    "kind": scenario.kind,
                    "description": scenario.description,
                    "assumptions": scenario.assumptions,
                    "uncertainty": scenario.uncertainty,
                    "safety": scenario.safety,
                    "impacts": scenario.impacts,
                    "result": modified,
                }
            )
        return self.results

    def compare(self, base_state: dict) -> List[Dict]:
        comparisons = []
        for result in self.results:
            impacts = result["impacts"]
            comparisons.append(
                {
                    "scenario": result["scenario"],
                    "kind": result["kind"],
                    "occupancy_delta": (
                        f"{impacts.get('occupancy_rate_delta', 0):+.2%}"
                    ),
                    "price_delta": f"Rs{impacts.get('price_delta', 0):+.2f}",
                    "congestion": result["result"].get(
                        "congestion_level", "unknown"
                    ),
                }
            )
        return comparisons
