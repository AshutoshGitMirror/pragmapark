import os
import re
import logging
from typing import Any, Optional
import numpy as np
import joblib
from src.constants import PRICE_FLOOR_RATIO, heuristic_price_multiplier
from src.rl.agent import NeuralAgent

logger = logging.getLogger(__name__)
DEFAULT_ZONE = "default"
AGENT_PATH: str = os.getenv(
    "RL_AGENT_PATH", "src/rl/artifacts/neural_agent.joblib"
)


class PricingController:
    def __init__(self, marl: Optional[Any] = None):
        self.agent: Any | None = None
        self._loaded: bool = False
        self.marl: Any | None = marl  # QMIXMARL instance when available

    def ensure(self) -> None:
        if not self._loaded:
            self._load()
            self._loaded = True

    def _load(self) -> None:
        try:
            agent = joblib.load(AGENT_PATH)
            if getattr(agent, 'state_size', 3) != 4:
                agent = NeuralAgent(state_size=4)
            self.agent = agent
            logger.info(f"Loaded single-agent DQN from {AGENT_PATH}")
        except Exception as e:
            logger.warning(f"Failed to load single-agent DQN: {e}")
            self.agent = None

    def _get_marl_multiplier(
        self, occupancy: float, current_price: float, zone_idx: int
    ) -> float:
        """Use zone-specific MARL agent to compute price multiplier.

        Paper: multi-agent RL provides per-zone pricing decisions informed
        by global state (all zones' occupancy and prices) via the QMIX
        hypernetwork mixing weights.
        """
        if not self.marl or zone_idx >= len(self.marl.agents):
            return heuristic_price_multiplier(occupancy)
        agent = self.marl.agents[zone_idx]
        state = np.array([occupancy, current_price, 0.5, 0.0])
        try:
            multiplier = float(agent.act(state, train=False))
        except Exception:
            logger.exception("event=rl.agent.fallback zone=%s", zone_idx)
            multiplier = heuristic_price_multiplier(occupancy)
        return multiplier

    def get_price(
        self,
        occupancy: float,
        current_price: float,
        price_cap: float = 200.0,
        zone_id: Optional[str] = None,
        resident_share_ratio: float = 0.0,
    ) -> tuple:
        """Compute price with optional per-zone MARL agent.

        Args:
            occupancy: current occupancy rate [0, 1]
            current_price: current price
            price_cap: maximum allowed price
            zone_id: zone identifier (e.g. 'zone_0', 'A1') — when provided
                     and MARL is initialized, uses the zone-specific agent.

        Returns:
            (new_price, multiplier) tuple
        """
        self.ensure()
        current_price = float(current_price)
        price_cap = float(price_cap)

        if self.marl and zone_id is not None:
            # Parse zone index from zone_id (e.g. 'zone_0' → 0, 'A1' → 1)
            zone_idx = self._parse_zone_idx(zone_id)
            multiplier = self._get_marl_multiplier(
                occupancy, current_price, zone_idx
            )
        elif self.agent:
            state = np.array([occupancy, current_price, 0.5, resident_share_ratio])
            multiplier = float(self.agent.act(state, train=False))
        else:
            logger.info(
                "event=pricing.heuristic.fallback occupancy=%.3f price=%.2f",
                occupancy,
                current_price,
            )
            multiplier = heuristic_price_multiplier(occupancy)

        new_price = np.clip(
            current_price * (1 + multiplier),
            max(current_price * PRICE_FLOOR_RATIO, 1.0),
            price_cap,
        )
        if self.marl and zone_id is not None:
            logger.debug(
                "event=pricing.marl zone=%s occupancy=%.3f "
                "multiplier=%.4f new_price=%.2f",
                zone_id,
                occupancy,
                multiplier,
                new_price,
            )
        return new_price, multiplier

    @staticmethod
    def _parse_zone_idx(zone_id: str) -> int:
        """Extract integer index from zone identifier."""
        # Try numeric suffix: 'zone_0' → 0, 'A1' → 1 (strip alpha prefix)
        nums = re.findall(r"\d+", zone_id)
        return int(nums[-1]) if nums else 0

    @property
    def agent_available(self) -> bool:
        return self.agent is not None or self.marl is not None

    @property
    def marl_available(self) -> bool:
        return self.marl is not None
