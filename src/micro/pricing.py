import logging
import numpy as np
from typing import Optional, Any
from src.constants import PROB_MULT_MIN, PROB_MULT_RANGE

logger = logging.getLogger(__name__)

DELTA_MAX_RATIO: float = 0.20
BASE_DIST_SCORE: float = 1.0

SLOT_TYPE_BASE: dict[str, float] = {
    "regular": 0.0,
    "ev": 0.05,
    "handicap": -0.10,
    "covered": 0.08,
    "premium": 0.15,
}


class SlotPricing:
    def compute_modifiers(self, slots: list[Any]) -> list[float]:
        if not slots:
            return []
        raw = []
        for s in slots:
            s_type = getattr(s, "slot_type", "regular")
            dist_score = getattr(s, "base_modifier_score", 0.0) or 0.0
            dist_factor = BASE_DIST_SCORE - dist_score
            type_bonus = SLOT_TYPE_BASE.get(s_type, 0.0)
            raw.append(dist_factor + type_bonus)
        arr = np.array(raw, dtype=float)
        arr = arr - arr.mean()
        arr = np.clip(arr, -DELTA_MAX_RATIO, DELTA_MAX_RATIO)
        return arr.tolist()

    def probability_multiplier(self, probability: float) -> float:
        p = max(0.0, min(1.0, probability))
        return round(PROB_MULT_MIN + p * PROB_MULT_RANGE, 4)

    def slot_price(
        self,
        slot: Any,
        base_price: float,
        modifiers: Optional[list] = None,
        probability: Optional[float] = None,
    ) -> float:
        if modifiers is not None:
            idx = getattr(slot, "slot_index", 0) - 1
            mod = modifiers[idx] if 0 <= idx < len(modifiers) else 0.0
        else:
            mod = getattr(slot, "current_modifier", 0.0) or 0.0
        base = float(base_price) * (1 + mod)
        if probability is not None:
            base *= self.probability_multiplier(probability)
        return round(base, 2)


slot_pricing = SlotPricing()
