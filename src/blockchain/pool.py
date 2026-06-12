import time
from typing import Callable, Dict, List, Optional
from .transaction import AllocationRecord
from src.constants import ALLOC_CONFIRMED, ALLOC_RELEASED


class ParkingPool:
    def __init__(
        self,
        pool_id: str,
        total_spots: int,
        owner: str,
        on_mutation: Optional[Callable[[], None]] = None,
    ):
        self.pool_id = pool_id
        self.total_spots = total_spots
        self.owner = owner
        self.allocations: Dict[str, AllocationRecord] = {}
        self.revenue_log: List[dict] = []
        self._on_mutation = on_mutation

    def _mark_dirty(self) -> None:
        if self._on_mutation is not None:
            self._on_mutation()

    def available_spots(self) -> int:
        active = sum(
            1 for a in self.allocations.values() if a.status == ALLOC_CONFIRMED
        )
        return self.total_spots - active

    def allocate(
        self, driver_id: str, lot_id: str, price: float, duration: int
    ) -> Optional[AllocationRecord]:
        if self.available_spots() <= 0:
            return None
        spot_id = f"{self.pool_id}-spot-{len(self.allocations) + 1}"
        record = AllocationRecord(
            driver_id=driver_id,
            lot_id=lot_id,
            spot_id=spot_id,
            allocated_price=price,
            start_time=time.time(),
            end_time=time.time() + duration * 60,
            status=ALLOC_CONFIRMED,
            revenue_share=price * 0.15,
        )
        self.allocations[spot_id] = record
        self.revenue_log.append(
            {
                "timestamp": time.time(),
                "driver_id": driver_id,
                "spot_id": spot_id,
                "price": price,
                "pool_share": record.revenue_share,
            }
        )
        self._mark_dirty()
        return record

    def release(self, spot_id: str) -> bool:
        if spot_id in self.allocations:
            self.allocations[spot_id].status = ALLOC_RELEASED
            self._mark_dirty()
            return True
        return False

    def total_revenue(self) -> float:
        return sum(r["price"] for r in self.revenue_log)

    def pool_revenue(self) -> float:
        return sum(r["pool_share"] for r in self.revenue_log)

    def to_dict(self) -> dict:
        return {
            "pool_id": self.pool_id,
            "total_spots": self.total_spots,
            "owner": self.owner,
            "available": self.available_spots(),
            "active_allocations": sum(
                1
                for a in self.allocations.values()
                if a.status == ALLOC_CONFIRMED
            ),
            "total_revenue": self.total_revenue(),
            "pool_revenue": self.pool_revenue(),
        }
