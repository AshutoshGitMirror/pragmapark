"""Digital twin simulator for parking zones."""

import numpy as np


class DigitalTwinSimulator:
    def __init__(self):
        self.zones = {}
        self.history = []

    def add_zone(self, zone_id: str, total_slots: int = 500):
        if zone_id not in self.zones:
            self.zones[zone_id] = {
                "zone_id": zone_id, "total_slots": total_slots,
                "occupancy_rate": 0.3, "price": 10.0,
                "available_slots": int(total_slots * 0.7),
                "congestion_level": "low",
            }

    def tick(self, pricing_signal: dict) -> list:
        states = []
        for zone_id, multiplier in pricing_signal.items():
            if zone_id not in self.zones:
                continue
            z = self.zones[zone_id]
            z["price"] = np.clip(z["price"] * (1 + multiplier * 0.1), 5, 50)
            drift = np.random.normal(0, 0.02)
            z["occupancy_rate"] = np.clip(
                z["occupancy_rate"] + multiplier * 0.05 + drift, 0.05, 0.95
            )
            z["available_slots"] = int(z["total_slots"] * (1 - z["occupancy_rate"]))
            if z["occupancy_rate"] > 0.85:
                z["congestion_level"] = "high"
            elif z["occupancy_rate"] > 0.6:
                z["congestion_level"] = "moderate"
            else:
                z["congestion_level"] = "low"
            states.append(dict(z))
        self.history.append(states)
        return states

    def get_zone_state(self, zone_id: str) -> dict:
        return self.zones.get(zone_id)

    def summary(self) -> dict:
        return {zid: z["congestion_level"] for zid, z in self.zones.items()}


class ScenarioEngine:
    def __init__(self):
        self.scenarios = {}

    def register_defaults(self):
        self.scenarios["zone_closure"] = self._zone_closure
        self.scenarios["surge_pricing"] = self._surge_pricing
        self.scenarios["weather_event"] = self._weather_event

    def _zone_closure(self, state: dict) -> dict:
        result = dict(state)
        result["total_slots"] = max(int(state["total_slots"] * 0.5), 1)
        result["occupancy_rate"] = min(state["occupancy_rate"] * 1.8, 1.0)
        result["available_slots"] = int(result["total_slots"] * (1 - result["occupancy_rate"]))
        return result

    def _surge_pricing(self, state: dict) -> dict:
        result = dict(state)
        result["price"] = state["price"] * 2.0
        result["occupancy_rate"] = max(state["occupancy_rate"] - 0.15, 0.05)
        result["available_slots"] = int(result["total_slots"] * (1 - result["occupancy_rate"]))
        return result

    def _weather_event(self, state: dict) -> dict:
        result = dict(state)
        reduction = np.random.uniform(0.1, 0.3)
        result["occupancy_rate"] = max(state["occupancy_rate"] - reduction, 0.05)
        result["available_slots"] = int(result["total_slots"] * (1 - result["occupancy_rate"]))
        result["price"] = state["price"] * 0.9
        return result

    def run_all(self, base_state: dict) -> list:
        return [
            {"scenario": name, **fn(base_state)}
            for name, fn in self.scenarios.items()
        ]

    def compare(self, base_state: dict) -> dict:
        return {
            name: {
                "occ_change": round(fn(base_state)["occupancy_rate"] - base_state["occupancy_rate"], 3),
                "price_change": round(fn(base_state)["price"] - base_state["price"], 2),
            }
            for name, fn in self.scenarios.items()
        }
