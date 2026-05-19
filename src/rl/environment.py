import numpy as np


class ParkingControlEnv:
    def __init__(self, zone_config: dict):
        self.zone_id = zone_config.get("zone_id", "zone_0")
        self.max_occupancy = zone_config.get("max_occupancy", 1.0)
        self.max_price = zone_config.get("max_price", 50.0)
        self.min_price = zone_config.get("min_price", 5.0)
        self.occupancy = None
        self.price = None

    def reset(self, occupancy: float = None) -> np.ndarray:
        if occupancy is not None:
            self.occupancy = occupancy
        else:
            self.occupancy = np.random.uniform(0.2, 0.8)
        self.price = np.random.uniform(self.min_price, self.max_price)
        return self._get_state()

    def _get_state(self) -> np.ndarray:
        if self.occupancy is None:
            self.occupancy = 0.5
        if self.price is None:
            self.price = 10.0
        return np.array([self.occupancy, self.price / self.max_price, 0.5]).reshape(1, 3)

    def step(self, action: int) -> tuple:
        price_multipliers = [-0.15, 0.0, 0.15]
        multiplier = price_multipliers[action]
        self.price = np.clip(self.price * (1 + multiplier), self.min_price, self.max_price)
        occ_change = -multiplier * 0.2 + np.random.normal(0, 0.02)
        self.occupancy = np.clip(self.occupancy + occ_change, 0.0, 1.0)

        if self.occupancy > 0.85:
            reward = -2.0 - abs(self.occupancy - 0.75) * 5
        elif self.occupancy < 0.3:
            reward = -1.0 - abs(self.occupancy - 0.75) * 3
        else:
            reward = 3.0 - abs(self.occupancy - 0.75) * 2

        done = bool(np.random.random() < 0.05)
        return self._get_state(), reward, done, {}
