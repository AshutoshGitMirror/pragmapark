import threading
import logging
from dataclasses import dataclass
from typing import Optional

from src.api.database import ResidentProfile, ShareListing, MicroSlot
from src.constants import SHARE_LISTING_ACTIVE, SHARE_LISTING_BOOKED

logger = logging.getLogger(__name__)


@dataclass
class ResidentSlotInfo:
    slot_id: int
    lot_id: str
    slot_index: int
    user_id: int
    registered_vehicle: Optional[str]
    is_shared: bool
    profile_id: int


class SlotResidentMapping:
    def __init__(self):
        self._lock = threading.Lock()
        self._by_slot_id: dict[int, ResidentSlotInfo] = {}
        self._by_user_id: dict[int, list[int]] = {}

    def register(self, slot_id: int, lot_id: str, slot_index: int,
                 user_id: int, registered_vehicle: Optional[str],
                 is_shared: bool, profile_id: int):
        info = ResidentSlotInfo(
            slot_id=slot_id,
            lot_id=lot_id,
            slot_index=slot_index,
            user_id=user_id,
            registered_vehicle=registered_vehicle,
            is_shared=is_shared,
            profile_id=profile_id,
        )
        with self._lock:
            self._by_slot_id[slot_id] = info
            self._by_user_id.setdefault(user_id, []).append(slot_id)

    def unregister(self, slot_id: int):
        with self._lock:
            info = self._by_slot_id.pop(slot_id, None)
            if info:
                slots = self._by_user_id.get(info.user_id, [])
                if slot_id in slots:
                    slots.remove(slot_id)
                    if not slots:
                        del self._by_user_id[info.user_id]

    def set_shared(self, slot_id: int, shared: bool):
        with self._lock:
            info = self._by_slot_id.get(slot_id)
            if info:
                info.is_shared = shared

    def is_resident_slot(self, slot_id: int) -> bool:
        return slot_id in self._by_slot_id

    def get_resident_info(self, slot_id: int) -> Optional[ResidentSlotInfo]:
        return self._by_slot_id.get(slot_id)

    def get_resident_slots(self, lot_id: str) -> list[ResidentSlotInfo]:
        return [
            info for info in self._by_slot_id.values()
            if info.lot_id == lot_id
        ]

    def get_resident_slots_by_user(self, user_id: int) -> list[ResidentSlotInfo]:
        slot_ids = self._by_user_id.get(user_id, [])
        return [self._by_slot_id[sid] for sid in slot_ids if sid in self._by_slot_id]

    def count_resident_only(self, lot_id: str) -> int:
        return sum(
            1 for info in self._by_slot_id.values()
            if info.lot_id == lot_id and not info.is_shared
        )

    def get_resident_only_slot_ids(self, lot_id: str) -> set[int]:
        return {
            sid for sid, info in self._by_slot_id.items()
            if info.lot_id == lot_id and not info.is_shared
        }

    def auth_check(self, lot_id: str, vehicle_id: str) -> list[ResidentSlotInfo]:
        return [
            info for info in self._by_slot_id.values()
            if info.lot_id == lot_id
            and info.registered_vehicle
            and info.registered_vehicle.upper() == vehicle_id.upper()
        ]

    def load_all(self, session):
        rows = (
            session.query(
                ResidentProfile.id,
                ResidentProfile.slot_id,
                ResidentProfile.user_id,
                ResidentProfile.registered_vehicle,
                MicroSlot.lot_id,
                MicroSlot.slot_index,
            )
            .join(MicroSlot, ResidentProfile.slot_id == MicroSlot.id)
            .filter(ResidentProfile.is_active == True)
            .all()
        )
        shared_slot_ids = {
            r.slot_id
            for r in session.query(ShareListing.slot_id)
            .filter(ShareListing.status.in_([SHARE_LISTING_ACTIVE, SHARE_LISTING_BOOKED]))
            .all()
        }
        with self._lock:
            self._by_slot_id.clear()
            self._by_user_id.clear()
            for r in rows:
                info = ResidentSlotInfo(
                    slot_id=r.slot_id,
                    lot_id=r.lot_id,
                    slot_index=r.slot_index,
                    user_id=r.user_id,
                    registered_vehicle=r.registered_vehicle,
                    is_shared=r.slot_id in shared_slot_ids,
                    profile_id=r.id,
                )
                self._by_slot_id[r.slot_id] = info
                self._by_user_id.setdefault(r.user_id, []).append(r.slot_id)
        logger.info(
            "event=resident_map.loaded count=%d shared=%d",
            len(rows), len(shared_slot_ids),
        )


slot_resident_mapping = SlotResidentMapping()
