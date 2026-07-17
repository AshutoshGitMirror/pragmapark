import numpy as np
from src.constants import (
    ACTION_MIN,
    ACTION_MAX,
    PRICE_MIN,
    PRICE_MAX,
    RL_DEFAULT_BASE_PRICE,
    RL_DEFAULT_VEHICLE_RATIO,
    RL_DEFAULT_RESIDENT_RATIO,
    CONGESTION_HIGH,
)


class ParkingControlEnv:
    def __init__(self, zone_data_row=None):
        self.zone_data = (
            zone_data_row
            if isinstance(zone_data_row, dict)
            else {
                "occupancy_rate": 0.5,
                "total_slots": 500,
            }
        )
        self.state = self._make_state(
            occupancy=self.zone_data.get("occupancy_rate", 0.5)
        )

    def _make_state(self, occupancy: float, resident_share_ratio: float = RL_DEFAULT_RESIDENT_RATIO) -> np.ndarray:
        return np.array(
            [[occupancy, RL_DEFAULT_BASE_PRICE, RL_DEFAULT_VEHICLE_RATIO, resident_share_ratio]]
        )

    def reset(self, occupancy: float = 0.5):
        self.state = self._make_state(occupancy)
        return self.state.copy()

    def step(self, action_multiplier: float):
        curr_occ = self.state[0][0]
        curr_price = self.state[0][1]

        price_mod = np.clip(action_multiplier, ACTION_MIN, ACTION_MAX)
        new_price = np.clip(curr_price * (1 + price_mod), PRICE_MIN, PRICE_MAX)

        elasticity = 0.8 * (new_price / 10.0)
        demand_impact = price_mod * elasticity
        new_occ = np.clip(
            curr_occ - demand_impact + np.random.normal(0, 0.01), 0, 1
        )

        capacity = self.zone_data.get("total_slots", 500)
        revenue = (new_occ * capacity) * new_price / 10000

        occ_bonus = 0.5 if 0.6 <= new_occ <= 0.8 else 0.0
        congestion_penalty = -1.0 if new_occ > CONGESTION_HIGH else 0.0
        greedy_penalty = -2.0 if new_price > 30 and new_occ < 0.4 else 0.0
        reward = revenue + occ_bonus + congestion_penalty + greedy_penalty

        self.state = self._make_state(new_occ)
        self.state[0][1] = new_price
        return self.state.copy(), reward, False, {"revenue": revenue}

    def get_state(self):
        return self.state[0].copy()
