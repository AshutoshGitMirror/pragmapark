#!/usr/bin/env python3
"""Generate 30 days of SlotStateLog history for all MicroSlots.

Run on first boot or when PRAGMA_FORCE_RESEED=true.
Creates realistic per-slot transitions with weekday/weekend/holiday patterns.
"""
import os
import sys
import random
import logging
from datetime import datetime, timedelta, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("generate_slot_history")

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.constants import is_holiday

# Occupancy profiles: hour -> (min_occ, max_occ)
WEEKDAY_PROFILE = {
    0: (0.03, 0.10), 1: (0.02, 0.08), 2: (0.02, 0.06), 3: (0.02, 0.05),
    4: (0.03, 0.08), 5: (0.05, 0.15), 6: (0.10, 0.30), 7: (0.25, 0.55),
    8: (0.55, 0.85), 9: (0.65, 0.90), 10: (0.70, 0.92), 11: (0.68, 0.88),
    12: (0.55, 0.80), 13: (0.50, 0.75), 14: (0.55, 0.80), 15: (0.60, 0.85),
    16: (0.65, 0.90), 17: (0.70, 0.95), 18: (0.50, 0.75), 19: (0.35, 0.60),
    20: (0.20, 0.45), 21: (0.12, 0.30), 22: (0.08, 0.20), 23: (0.05, 0.12),
}

WEEKEND_PROFILE = {
    0: (0.05, 0.15), 1: (0.04, 0.12), 2: (0.03, 0.10), 3: (0.03, 0.08),
    4: (0.04, 0.10), 5: (0.05, 0.12), 6: (0.08, 0.20), 7: (0.12, 0.30),
    8: (0.20, 0.45), 9: (0.30, 0.55), 10: (0.40, 0.65), 11: (0.50, 0.75),
    12: (0.55, 0.80), 13: (0.55, 0.78), 14: (0.50, 0.75), 15: (0.45, 0.70),
    16: (0.40, 0.65), 17: (0.35, 0.55), 18: (0.30, 0.50), 19: (0.25, 0.45),
    20: (0.18, 0.35), 21: (0.12, 0.25), 22: (0.08, 0.18), 23: (0.06, 0.12),
}

HOLIDAY_PROFILE = {
    0: (0.08, 0.18), 1: (0.06, 0.14), 2: (0.05, 0.12), 3: (0.04, 0.10),
    4: (0.05, 0.12), 5: (0.06, 0.14), 6: (0.10, 0.22), 7: (0.15, 0.32),
    8: (0.22, 0.48), 9: (0.32, 0.58), 10: (0.42, 0.68), 11: (0.52, 0.76),
    12: (0.58, 0.82), 13: (0.55, 0.80), 14: (0.52, 0.76), 15: (0.48, 0.72),
    16: (0.42, 0.68), 17: (0.38, 0.58), 18: (0.32, 0.52), 19: (0.28, 0.48),
    20: (0.20, 0.38), 21: (0.14, 0.28), 22: (0.10, 0.20), 23: (0.08, 0.15),
}

# Slot state transitions
# From state -> possible (to_state, weight)
TRANSITIONS = {
    "available": [("occupied", 1.0)],
    "occupied": [("available", 0.8), ("occupied", 0.2)],
}


def get_profile(dt: datetime) -> dict:
    if is_holiday(dt):
        return HOLIDAY_PROFILE
    if dt.weekday() >= 5:
        return WEEKEND_PROFILE
    return WEEKDAY_PROFILE


def generate_transitions_for_slot(slot_id: int, lot_id: str, num_days: int, now: datetime):
    """Generate a list of SlotStateLog dicts for one slot over num_days."""
    records = []
    current_state = "available"
    current_time = now - timedelta(days=num_days)

    while current_time < now:
        profile = get_profile(current_time)
        hour = current_time.hour
        occ_min, occ_max = profile.get(hour, (0.1, 0.5))
        target_occ = random.uniform(occ_min, occ_max)

        # Decide how many transitions in this hour
        num_transitions = max(1, int(target_occ * random.randint(2, 6)))

        for _ in range(num_transitions):
            # Gap between transitions: 5-45 minutes
            gap_minutes = random.randint(5, 45)
            current_time += timedelta(minutes=gap_minutes)
            if current_time >= now:
                break

            # Pick next state
            options = TRANSITIONS.get(current_state, [("available", 1.0)])
            r = random.random()
            cumulative = 0.0
            next_state = options[0][0]
            for to_state, weight in options:
                cumulative += weight
                if r <= cumulative:
                    next_state = to_state
                    break

            duration_s = gap_minutes * 60 * random.uniform(0.5, 1.5)
            driver_id = f"driver_{random.randint(1, 200)}" if next_state == "occupied" else None

            records.append({
                "slot_id": slot_id,
                "lot_id": lot_id,
                "previous_state": current_state,
                "new_state": next_state,
                "timestamp": current_time,
                "duration_s": round(duration_s, 1),
                "driver_id": driver_id,
            })
            current_state = next_state

    return records


def seed_history(num_days: int | None = None):
    if num_days is None:
        num_days = int(os.getenv("PRAGMA_HISTORY_DAYS", "30"))

    from src.api.database import get_db_cm, MicroSlot, SlotStateLog, ParkingLot

    with get_db_cm() as db:
        # Check if history already exists
        existing = db.query(SlotStateLog).count()
        if existing > 0:
            log.info("SlotStateLog already has %d records — skipping", existing)
            return

        lots = db.query(ParkingLot).all()
        if not lots:
            log.warning("No lots found — skipping SlotStateLog generation")
            return

        total_records = 0
        now = datetime.now(timezone.utc)

        for lot in lots:
            slots = db.query(MicroSlot).filter(MicroSlot.lot_id == lot.lot_id).all()
            if not slots:
                continue

            all_records = []
            for slot in slots:
                records = generate_transitions_for_slot(slot.id, lot.lot_id, num_days, now)
                all_records.extend(records)

            # Batch insert
            for r in all_records:
                db.add(SlotStateLog(**r))
            total_records += len(all_records)
            log.info("Generated %d transitions for lot %s (%d slots)", len(all_records), lot.lot_id, len(slots))

        db.commit()
        log.info("SlotStateLog generation complete: %d total records across %d lots", total_records, len(lots))


if __name__ == "__main__":
    seed_history()
