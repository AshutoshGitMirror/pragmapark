import os
import logging
import numpy as np
import joblib
from src.constants import PRICE_FLOOR_RATIO, heuristic_price_multiplier

logger = logging.getLogger(__name__)
AGENT_PATH = os.getenv("RL_AGENT_PATH", "src/rl/artifacts/neural_agent.joblib")


class PricingController:
    def __init__(self):
        self.agent = None
        self._loaded = False

    def ensure(self):
        if not self._loaded:
            self._load()
            self._loaded = True

    def _load(self):
        try:
            self.agent = joblib.load(AGENT_PATH)
            logger.info(f"Loaded RL agent from {AGENT_PATH}")
        except Exception as e:
            logger.warning(f"Failed to load RL agent: {e}")
            self.agent = None

    def get_price(self, occupancy: float, current_price: float, price_cap: float = 200.0) -> tuple:
        self.ensure()
        current_price = float(current_price)
        price_cap = float(price_cap)
        if self.agent:
            state = np.array([occupancy, current_price, 0.5])
            multiplier = float(self.agent.act(state, train=False))
        else:
            multiplier = heuristic_price_multiplier(occupancy)
        new_price = np.clip(
            current_price * (1 + multiplier),
            max(current_price * PRICE_FLOOR_RATIO, 1.0),
            price_cap,
        )
        return new_price, multiplier

    @property
    def agent_available(self) -> bool:
        return self.agent is not None
