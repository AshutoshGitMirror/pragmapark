import logging
from datetime import datetime, timezone
from typing import Optional, Any

from src.micro.models import SlotState
from src.micro.state_engine import slot_state_engine

logger = logging.getLogger(__name__)

LOOKAHEAD_S: int = 900
BASE_DECAY: float = 0.003
PROB_WEIGHT: int = 10
PRICE_PENALTY: float = 0.05
NUM_HOUR_BUCKETS: int = 24


def _hour_bucket(dt: datetime) -> int:
    return dt.hour % NUM_HOUR_BUCKETS


class SlotPredictor:
    def __init__(self):
        self._alpha: dict[tuple[int, int], float] = {}
        self._beta: dict[tuple[int, int], float] = {}
        self._loaded: set[int] = set()

    def _load_historical(self, slot_id: int) -> None:
        try:
            from src.api.database import get_session, SlotStateLog
            db = get_session()
            try:
                records = db.query(SlotStateLog).filter(
                    SlotStateLog.slot_id == slot_id,
                ).order_by(SlotStateLog.timestamp.desc()).limit(500).all()
                for r in records:
                    hb = _hour_bucket(r.timestamp) if r.timestamp else 0
                    key = (slot_id, hb)
                    a = self._alpha.get(key, 2.0)
                    b = self._beta.get(key, 2.0)
                    if r.previous_state == "occupied" and r.new_state == "available":
                        self._alpha[key] = a + 1.0
                    elif r.previous_state == "available" and r.new_state == "occupied":
                        self._beta[key] = b + 1.0
                    else:
                        self._alpha[key] = a + 0.5
                        self._beta[key] = b + 0.5
            finally:
                db.close()
        except Exception as e:
            logger.warning("Failed to load historical data for slot %d: %s", slot_id, e)

    def record_transition(self, slot_id: int, prev_state: str, new_state: str, timestamp: Optional[datetime] = None) -> None:
        hb = _hour_bucket(timestamp or datetime.now(timezone.utc))
        key = (slot_id, hb)
        a = self._alpha.get(key, 2.0)
        b = self._beta.get(key, 2.0)
        if prev_state == "occupied" and new_state == "available":
            self._alpha[key] = a + 1.0
        elif prev_state == "available" and new_state == "occupied":
            self._beta[key] = b + 1.0
        else:
            self._alpha[key] = a + 0.5
            self._beta[key] = b + 0.5

    def predict(self, slot_id: int, target_time: Optional[str] = None) -> float:
        state = slot_state_engine.get_state(slot_id)
        if state in (SlotState.OCCUPIED, SlotState.MAINTENANCE):
            return 0.0
        if target_time is not None:
            try:
                target = datetime.fromisoformat(target_time)
            except (ValueError, TypeError):
                target = datetime.now(timezone.utc)
        else:
            target = datetime.now(timezone.utc)
        hb = _hour_bucket(target)
        key = (slot_id, hb)
        if slot_id not in self._loaded:
            self._load_historical(slot_id)
            self._loaded.add(slot_id)
        a = self._alpha.get(key, 2.0)
        b = self._beta.get(key, 2.0)
        base = a / (a + b) if (a + b) > 0 else 0.5
        secs = max(0.0, (target - datetime.now(timezone.utc)).total_seconds())
        if secs > 3600:
            decayed = 0.5
        else:
            decayed = max(0.1, base - secs * BASE_DECAY)
        if state == SlotState.RESERVED:
            remaining = slot_state_engine.get_reservation_remaining(slot_id)
            decayed = 0.9 if remaining <= 0 else max(0.1, 1.0 - secs * BASE_DECAY * 2)
        elif state == SlotState.PREBOOKED:
            decayed = 0.95
        return round(min(1.0, max(0.0, decayed)), 4)

    def predict_zone(self, slot_ids: list[int], target_time: Optional[str] = None) -> dict[int, float]:
        return {sid: self.predict(sid, target_time) for sid in slot_ids}

    def best_slots(self, slots: list[Any], base_price: float, top_k: int = 5,
                   target_time: Optional[str] = None) -> list[dict[str, Any]]:
        scored = []
        for s in slots:
            prob = self.predict(s.id, target_time)
            from src.micro.pricing import slot_pricing
            price = float(slot_pricing.slot_price(s, base_price))
            scored.append({
                "slot_id": s.id, "slot_label": f"{s.row_label}{s.position}",
                "probability": prob, "price": price,
                "score": prob * PROB_WEIGHT - price * PRICE_PENALTY,
            })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]


slot_predictor = SlotPredictor()
