from enum import Enum


class SlotState(str, Enum):
    AVAILABLE = "available"
    PREBOOKED = "prebooked"
    RESERVED = "reserved"
    OCCUPIED = "occupied"
    MAINTENANCE = "maintenance"


class SlotType(str, Enum):
    REGULAR = "regular"
    EV = "ev"
    HANDICAP = "handicap"
    COVERED = "covered"
    PREMIUM = "premium"
