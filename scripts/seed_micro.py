"""Seed micro-slots and micro-zones for all parking lots."""
import os
import sys
import math
import random
sys.path.insert(0, ".")

from src.api.database import get_session, ParkingLot, MicroSlot, MicroZone

LOT_SIZES = {
    "A1": 500, "A2": 350, "B1": 200, "B2": 600,
    "C1": 300, "C2": 400,
    "L1": 800, "L2": 600,
    "M1": 400, "M2": 300,
    "NY1": 1000, "NY2": 500,
    "SF1": 600, "SF2": 350,
    "TK1": 300, "TK2": 400,
    "DB1": 1500, "DB2": 700,
    "SG1": 500, "SG2": 600,
    "MB1": 700, "MB2": 400,
    "BR1": 500, "BR2": 400,
}

def seed():
    db = get_session()
    lots = db.query(ParkingLot).all()
    if not lots:
        print("No lots found — run seed_data.py first")
        sys.exit(1)

    total_seeded = 0
    for lot in lots:
        existing = db.query(MicroSlot).filter(MicroSlot.lot_id == lot.lot_id).count()
        if existing > 0:
            print(f"Skipped {lot.lot_id}: {existing} slots already exist")
            continue

        z = MicroZone(lot_id=lot.lot_id, name="Default", description="Auto-generated zone")
        db.add(z)
        db.flush()

        total = LOT_SIZES.get(lot.lot_id, lot.total_slots)
        rows = max(1, math.ceil(total / 20))
        per_row = math.ceil(total / rows)
        created = 0
        for r in range(rows):
            row_label = chr(65 + r) if r < 26 else f"Z{r}"
            for p in range(per_row):
                if created >= total:
                    break
                roll = random.random()
                if roll < 0.05:
                    s_type = "handicap"
                elif roll < 0.10:
                    s_type = "ev"
                elif roll < 0.25:
                    s_type = "covered"
                elif roll < 0.30:
                    s_type = "premium"
                else:
                    s_type = "regular"
                ms = MicroSlot(
                    lot_id=lot.lot_id, slot_index=created + 1,
                    micro_zone_id=z.id, row_label=row_label,
                    position=p + 1, slot_type=s_type, active=1,
                    base_modifier_score=random.uniform(0, 0.5),
                )
                db.add(ms)
                created += 1
        db.commit()
        print(f"Seeded {created} micro slots for {lot.lot_id} ({lot.name})")
        total_seeded += created

    db.close()
    print(f"\nDone — {total_seeded} slots across {len(lots)} lots")

if __name__ == "__main__":
    if os.environ.get("PRAGMA_ENV") == "production":
        print("Refusing to seed in production")
        sys.exit(1)
    seed()
