"""
Minimal seed data generator — structural entities only.

Creates parking lots, micro zones/slots, and driver accounts.
No occupancy, sessions, transactions, predictions, revenue,
prebooks, ledger outbox, or slot state logs.
"""

import logging

from src.api.database import (
    ParkingLot,
    MicroZone,
    MicroSlot,
    User,
    get_session,
)
from src.api.auth import hash_password

logger = logging.getLogger(__name__)

# Lot definitions — single source of truth
# (lot_id, name, address, city, slots, lat, lng, base_price, price_cap)
SEED_LOTS = [
    ("A1", "Downtown Plaza",      "123 Main St",      "Birmingham", 500, 52.48, -1.89, 15.0, 50.0),
    ("A2", "Station Approach",    "45 Railway Rd",    "Birmingham", 350, 52.47, -1.90, 12.0, 45.0),
    ("L1", "Canary Wharf Garage", "1 Bank St",        "London",     800, 51.50, -0.02, 25.0, 80.0),
    ("L2", "King's Cross",        "90 Euston Rd",     "London",     600, 51.53, -0.12, 20.0, 65.0),
    ("MB1","BKC Lot",             "Bandra Kurla Complex","Mumbai",  700, 19.07, 72.87, 12.0, 30.0),
    ("MB2","Nariman Point",       "1 Nariman Point",    "Mumbai",   400, 18.93, 72.82, 10.0, 25.0),
]

ZONE_NAMES = {
    "A1": ["North Wing", "South Terrace", "East Deck"],
    "A2": ["Main Floor", "Lower Level", "Express Zone"],
    "L1": ["Tower A", "Tower B", "Plaza Level", "Basement"],
    "L2": ["Front Lot", "Rear Yard", "Overflow"],
    "MB1": ["Airside", "Landside", "Premium Row", "General"],
    "MB2": ["West Wing", "East Wing", "Compact"],
}


def seed_all(session, days: int = 30) -> dict:
    """Create structural entities only: lots, zones, slots, drivers.
    The ``days`` parameter is accepted for backward compatibility but
    ignored — no time-series data is generated.
    """
    # ─── Step 0: Wipe generated data (keep User) ───
    for table in [
        MicroSlot,
        MicroZone,
        ParkingLot,
    ]:
        session.query(table).delete()
    session.commit()

    # ─── Step 1: Ensure seed drivers exist (keep existing) ───
    drivers = []
    for email, name in [
        ("driver@pragma.io", "Alice Driver"),
        ("carol@pragma.io", "Carol Parker"),
        ("bob@pragma.io", "Bob Singh"),
    ]:
        u = session.query(User).filter(User.email == email).first()
        if u:
            u.balance = 5000.0
            u.full_name = name
            u.hashed_password = hash_password("driver123")
            drivers.append(u)
        else:
            u = User(
                email=email,
                hashed_password=hash_password("driver123"),
                full_name=name,
                role="driver",
                balance=5000.0,
            )
            session.add(u)
            session.flush()
            drivers.append(u)
    session.commit()

    # ─── Step 2: Create lots ───
    for rec in SEED_LOTS:
        lot_id, name, address, city, slots, lat, lng, bp, pc = rec
        pl = ParkingLot(
            lot_id=lot_id,
            name=name,
            address=address,
            city=city,
            total_slots=slots,
            latitude=lat,
            longitude=lng,
            base_price=str(bp),
            price_cap=str(pc),
        )
        session.add(pl)
    session.commit()

    # ─── Step 3: Micro zones + slots ───
    for rec in SEED_LOTS:
        lot_id = rec[0]
        slots_count = rec[4]
        znames = ZONE_NAMES.get(lot_id, ["Zone A", "Zone B"])
        nzones = min(len(znames), max(1, slots_count // 150))
        zones = []
        for zi in range(nzones):
            z = MicroZone(
                lot_id=lot_id,
                name=znames[zi],
                description=f"{znames[zi]} — capacity ~{slots_count // nzones}",
            )
            session.add(z)
            session.flush()
            zones.append(z)

        for si in range(slots_count):
            zi = si % max(1, len(zones))
            row_label = chr(65 + (si // 20) % 26)
            st = "regular"
            mod = 0.0
            ms = MicroSlot(
                lot_id=lot_id,
                slot_index=si,
                micro_zone_id=zones[zi].id,
                row_label=row_label,
                position=si % 20,
                slot_type=st,
                active=1,
                base_modifier_score=round(mod, 2),
                current_modifier=round(mod, 2),
            )
            session.add(ms)
            session.flush()

    session.commit()

    return {
        "status": "seeded",
        "lots_created": len(SEED_LOTS),
        "occupancy_records": 0,
        "sessions": 0,
        "transactions": 0,
        "drivers": len(drivers),
    }


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    session = get_session()
    report = seed_all(session)
    print(json.dumps(report, indent=2))
