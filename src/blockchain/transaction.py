import time
import hashlib
from dataclasses import dataclass, field
from typing import Optional

from src.constants import ALLOC_CONFIRMED


@dataclass
class ParkingTransaction:
    driver_id: str
    lot_id: str
    spot_id: str
    action: str
    price: float
    duration_minutes: int
    timestamp: float = field(default_factory=time.time)
    tx_hash: Optional[str] = None
    previous_hash: Optional[str] = None

    def __post_init__(self):
        if self.tx_hash is None:
            self.tx_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        raw = f"{self.driver_id}{self.lot_id}{self.spot_id}{self.action}{
            self.price
        }{self.duration_minutes}{self.timestamp}{self.previous_hash or ''}"
        # full 256-bit (64 hex chars)
        return hashlib.sha256(raw.encode()).hexdigest()


@dataclass
class AllocationRecord:
    driver_id: str
    lot_id: str
    spot_id: str
    allocated_price: float
    start_time: float
    end_time: float
    status: str = ALLOC_CONFIRMED
    revenue_share: float = 0.0

    def elapsed_minutes(self) -> float:
        return (time.time() - self.start_time) / 60.0

    def to_dict(self) -> dict:
        return {
            "driver_id": self.driver_id,
            "lot_id": self.lot_id,
            "spot_id": self.spot_id,
            "allocated_price": self.allocated_price,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "status": self.status,
            "revenue_share": self.revenue_share,
        }
