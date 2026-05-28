import numpy as np
import pandas as pd
from typing import List, Optional
from collections import deque
from dataclasses import dataclass
from src.constants import CONGESTION_HIGH, CONGESTION_MODERATE, CONGESTION_LOW


@dataclass
class TwinState:
    timestamp: float
    zone_id: str
    occupancy_rate: float
    price: float
    total_slots: int
    flux: float = 0.0
    congestion_level: str = "normal"


class DigitalTwinSimulator:
    def __init__(self, historical_data: Optional[pd.DataFrame] = None):
        self.historical_data = historical_data
        self.state_history: deque = deque(maxlen=1000)
        self.current_time: float = 0.0
        self.zones: dict = {}

    def initialize_from_data(self, data: pd.DataFrame) -> None:
        self.historical_data = data
        for _, row in data.iterrows():
            zone_id = row.get("lot_id", "zone_0")
            if zone_id not in self.zones:
                self.zones[zone_id] = {
                    "capacity": row.get("total_slots", 500),
                    "occupancy": row.get("occupancy_rate", 0.5),
                    "price": 10.0,
                }
        print(f"  DT Initialized: {len(self.zones)} zones from data")

    def add_zone(self, zone_id: str, capacity: int) -> None:
        self.zones[zone_id] = {"capacity": capacity, "occupancy": 0.3, "price": 10.0}

    def tick(self, price_adjustments: Optional[dict] = None) -> List[TwinState]:
        states = []
        for zone_id, zone in self.zones.items():
            prev_occ = zone["occupancy"]
            adjustment = (price_adjustments or {}).get(zone_id, 0.0)
            zone["price"] = np.clip(zone["price"] * (1 + adjustment), 5, 50)

            elasticity = 0.8 * (zone["price"] / 10.0)
            demand_impact = adjustment * elasticity
            noise = np.random.normal(0, 0.015)
            zone["occupancy"] = np.clip(zone["occupancy"] - demand_impact + noise, 0, 1)

            flux = zone["occupancy"] - prev_occ

            if zone["occupancy"] > CONGESTION_HIGH:
                congestion = "critical"
            elif zone["occupancy"] > CONGESTION_MODERATE:
                congestion = "high"
            elif zone["occupancy"] > CONGESTION_LOW:
                congestion = "moderate"
            else:
                congestion = "normal"

            state = TwinState(
                timestamp=self.current_time,
                zone_id=zone_id,
                occupancy_rate=zone["occupancy"],
                price=zone["price"],
                total_slots=zone["capacity"],
                flux=flux,
                congestion_level=congestion,
            )
            states.append(state)
            self.state_history.append(state)

        self.current_time += 1
        return states

    def get_zone_state(self, zone_id: str) -> Optional[dict]:
        zone = self.zones.get(zone_id)
        if zone is None:
            return None
        return {
            "zone_id": zone_id,
            "capacity": zone["capacity"],
            "occupancy_rate": zone["occupancy"],
            "price": zone["price"],
            "available_slots": int(zone["capacity"] * (1 - zone["occupancy"])),
        }

    def summary(self) -> dict:
        if not self.zones:
            return {"status": "empty", "zones": 0}
        occs = [z["occupancy"] for z in self.zones.values()]
        prices = [z["price"] for z in self.zones.values()]
        return {
            "zones": len(self.zones),
            "mean_occupancy": float(np.mean(occs)),
            "std_occupancy": float(np.std(occs)),
            "mean_price": float(np.mean(prices)),
            "history_length": len(self.state_history),
            "congestion_alerts": sum(
                1 for s in self.state_history if s.congestion_level == "critical"
            ),
        }
