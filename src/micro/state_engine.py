import time
import threading
import logging
import os
from typing import Optional, Callable, Any

from src.micro.models import SlotState

logger = logging.getLogger(__name__)

RESERVATION_TTL_S: int = int(os.getenv("RESERVATION_TTL_S", "300"))
CLEANUP_INTERVAL_S: int = int(os.getenv("CLEANUP_INTERVAL_S", "60"))
MAX_PREBOOK_HOURS: int = int(os.getenv("MAX_PREBOOK_HOURS", "12"))
PREBOOK_GRACE_S: int = int(os.getenv("PREBOOK_GRACE_S", "1800"))


class SlotStateEngine:
    def __init__(self):
        self._lock = threading.Lock()
        self._states: dict[int, SlotState] = {}
        self._timestamps: dict[int, float] = {}
        self._reservations: dict[int, str] = {}
        self._reservation_expiry: dict[int, float] = {}
        self._prebook_drivers: dict[int, str] = {}
        self._prebook_expiry: dict[int, float] = {}
        self._prebook_target: dict[int, float] = {}
        self._last_cleanup = time.time()
        self._on_transition: Optional[Callable[[int, str, str, str], None]] = None

    def _expire_one(self, sid: int) -> None:
        exp = self._reservation_expiry.get(sid)
        if exp is not None and time.time() > exp:
            self._states[sid] = SlotState.AVAILABLE
            self._reservations.pop(sid, None)
            self._reservation_expiry.pop(sid, None)
            self._prebook_drivers.pop(sid, None)
            self._prebook_expiry.pop(sid, None)
            self._prebook_target.pop(sid, None)

    def _expire_one_prebook(self, sid: int) -> bool:
        exp = self._prebook_expiry.get(sid)
        if exp is not None and time.time() > exp:
            self._states[sid] = SlotState.AVAILABLE
            self._prebook_drivers.pop(sid, None)
            self._prebook_expiry.pop(sid, None)
            self._prebook_target.pop(sid, None)
            return True
        target = self._prebook_target.get(sid)
        if target is not None and time.time() > target:
            state = self._states.get(sid)
            if state == SlotState.PREBOOKED:
                self._states[sid] = SlotState.RESERVED
                self._reservation_expiry[sid] = self._prebook_expiry.get(sid, time.time() + PREBOOK_GRACE_S)
        return False

    def _do_cleanup(self, now: float) -> None:
        expired_reservations = [s for s in list(self._reservation_expiry) if now > self._reservation_expiry[s]]
        for sid in expired_reservations:
            self._states[sid] = SlotState.AVAILABLE
            self._reservations.pop(sid, None)
            self._reservation_expiry.pop(sid, None)
            self._prebook_drivers.pop(sid, None)
            self._prebook_expiry.pop(sid, None)
            self._prebook_target.pop(sid, None)
        if expired_reservations:
            logger.info("Cleaned up %d expired reservations", len(expired_reservations))
        for sid in list(self._prebook_target):
            target = self._prebook_target[sid]
            if now > target and self._states.get(sid) == SlotState.PREBOOKED:
                self._states[sid] = SlotState.RESERVED
                self._reservation_expiry[sid] = self._prebook_expiry.get(sid, now + PREBOOK_GRACE_S)
        expired_prebooks = [s for s in list(self._prebook_expiry) if now > self._prebook_expiry[s]]
        for sid in expired_prebooks:
            self._states[sid] = SlotState.AVAILABLE
            self._prebook_drivers.pop(sid, None)
            self._prebook_expiry.pop(sid, None)
            self._prebook_target.pop(sid, None)
        if expired_prebooks:
            logger.info("Cleaned up %d expired prebookings", len(expired_prebooks))

    def _cleanup_batch(self) -> None:
        now = time.time()
        if now - self._last_cleanup < CLEANUP_INTERVAL_S:
            return
        self._last_cleanup = now
        with self._lock:
            self._do_cleanup(now)

    def on_transition(self, callback: Optional[Callable[[int, str, str, str], None]]) -> None:
        self._on_transition = callback

    def set_state(self, slot_id: int, state: SlotState) -> None:
        with self._lock:
            prev = self._states.get(slot_id)
            self._states[slot_id] = state
            self._timestamps[slot_id] = time.time()
            if state == SlotState.AVAILABLE:
                self._reservations.pop(slot_id, None)
                self._reservation_expiry.pop(slot_id, None)
                self._prebook_drivers.pop(slot_id, None)
                self._prebook_expiry.pop(slot_id, None)
                self._prebook_target.pop(slot_id, None)
            if self._on_transition:
                self._on_transition(slot_id, prev.value if prev else "", state.value, "")

    def get_state(self, slot_id: int) -> SlotState:
        with self._lock:
            return self._states.get(slot_id, SlotState.AVAILABLE)

    def reserve(self, slot_id: int, driver_id: str, ttl_s: int = RESERVATION_TTL_S) -> bool:
        self._cleanup_batch()
        with self._lock:
            self._expire_one(slot_id)
            cur = self._states.get(slot_id, SlotState.AVAILABLE)
            if cur != SlotState.AVAILABLE:
                return False
            self._states[slot_id] = SlotState.RESERVED
            self._timestamps[slot_id] = time.time()
            self._reservations[slot_id] = driver_id
            self._reservation_expiry[slot_id] = time.time() + ttl_s
            return True

    def release(self, slot_id: int, driver_id: str) -> bool:
        with self._lock:
            if self._reservations.get(slot_id) != driver_id:
                return False
            self._states[slot_id] = SlotState.AVAILABLE
            self._timestamps[slot_id] = time.time()
            self._reservations.pop(slot_id, None)
            self._reservation_expiry.pop(slot_id, None)
            return True

    def prebook(self, slot_id: int, driver_id: str, target_time_mono: float) -> bool:
        max_target = time.time() + MAX_PREBOOK_HOURS * 3600
        if target_time_mono > max_target:
            return False
        self._cleanup_batch()
        with self._lock:
            self._expire_one_prebook(slot_id)
            cur = self._states.get(slot_id, SlotState.AVAILABLE)
            if cur != SlotState.AVAILABLE:
                return False
            self._states[slot_id] = SlotState.PREBOOKED
            self._timestamps[slot_id] = time.time()
            self._prebook_drivers[slot_id] = driver_id
            self._prebook_target[slot_id] = target_time_mono
            self._prebook_expiry[slot_id] = target_time_mono + PREBOOK_GRACE_S
            return True

    def confirm_prebook(self, slot_id: int, driver_id: str) -> bool:
        self._cleanup_batch()
        with self._lock:
            if self._prebook_drivers.get(slot_id) != driver_id:
                return False
            if self._expire_one_prebook(slot_id):
                return False
            cur = self._states.get(slot_id, SlotState.AVAILABLE)
            if cur not in (SlotState.PREBOOKED, SlotState.RESERVED, SlotState.OCCUPIED):
                return False
            self._states[slot_id] = SlotState.OCCUPIED
            self._timestamps[slot_id] = time.time()
            self._prebook_drivers.pop(slot_id, None)
            self._prebook_expiry.pop(slot_id, None)
            self._prebook_target.pop(slot_id, None)
            return True

    def release_prebook(self, slot_id: int, driver_id: str) -> bool:
        with self._lock:
            if self._prebook_drivers.get(slot_id) != driver_id:
                return False
            self._states[slot_id] = SlotState.AVAILABLE
            self._timestamps[slot_id] = time.time()
            self._prebook_drivers.pop(slot_id, None)
            self._prebook_expiry.pop(slot_id, None)
            self._prebook_target.pop(slot_id, None)
            return True

    def is_reserved_by(self, slot_id: int, driver_id: str) -> bool:
        with self._lock:
            return self._reservations.get(slot_id) == driver_id

    def get_reservation_remaining(self, slot_id: int) -> float:
        with self._lock:
            return max(0.0, self._reservation_expiry.get(slot_id, 0.0) - time.time())

    def occupancies(self, lot_id: str = "", slots: Optional[list[Any]] = None) -> dict[str, Any]:
        total = avail = reserv = occup = prebook = 0
        for s in (slots or []):
            total += 1
            st = self.get_state(s.id)
            if st == SlotState.AVAILABLE:
                avail += 1
            elif st == SlotState.RESERVED:
                reserv += 1
            elif st == SlotState.OCCUPIED:
                occup += 1
            elif st == SlotState.PREBOOKED:
                prebook += 1
        return dict(total_slots=total, available_slots=avail, reserved_slots=reserv,
                    occupied_slots=occup, prebooked_slots=prebook,
                    occupancy_rate=round(occup / total, 4) if total else 0.0)

    def bulk_set_occupied(self, occupied_set: set[int], all_slots: list) -> None:
        with self._lock:
            now = time.time()
            for s in all_slots:
                was = self._states.get(s.id)
                if s.id in occupied_set:
                    self._states[s.id] = SlotState.OCCUPIED
                elif was != SlotState.RESERVED:
                    self._states[s.id] = SlotState.AVAILABLE
                self._timestamps[s.id] = now

    def cleanup_expired(self, force: bool = False) -> None:
        if force:
            now = time.time()
            with self._lock:
                self._do_cleanup(now)
        else:
            self._cleanup_batch()


    def clear_prebook_state(self, slot_id: int, driver_id: str) -> bool:
        with self._lock:
            if self._prebook_drivers.get(slot_id) != driver_id:
                return False
            self._prebook_drivers.pop(slot_id, None)
            self._prebook_expiry.pop(slot_id, None)
            self._prebook_target.pop(slot_id, None)
            return True

    def is_prebooked_by(self, slot_id: int, driver_id: str) -> bool:
        with self._lock:
            return self._prebook_drivers.get(slot_id) == driver_id

    def get_prebook_status(self, slot_id: int) -> dict:
        with self._lock:
            return dict(
                is_prebooked=slot_id in self._prebook_drivers,
                driver=self._prebook_drivers.get(slot_id, ""),
                target_time=self._prebook_target.get(slot_id, 0.0),
                expires_at=self._prebook_expiry.get(slot_id, 0.0),
                remaining=max(0.0, self._prebook_expiry.get(slot_id, 0.0) - time.time()) if slot_id in self._prebook_expiry else 0.0,
            )


slot_state_engine = SlotStateEngine()
