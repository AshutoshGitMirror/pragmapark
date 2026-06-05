"""Seed the Pragma database with demo data."""
import os
import sys
import random
from datetime import datetime, timedelta, timezone
sys.path.insert(0, ".")

from src.api.database import get_session, ParkingLot, OccupancyRecord, Transaction, RevenueRecord, User
from src.api.auth import hash_password

LOTS = [
    # Birmingham, UK
    ("A1", "Downtown Plaza", "123 Main St", 500, 52.48, -1.89, 15.0, "Birmingham", 50.0),
    ("A2", "Station Approach", "45 Railway Rd", 350, 52.47, -1.90, 12.0, "Birmingham", 45.0),
    ("B1", "Market Square", "78 Market St", 200, 52.48, -1.88, 10.0, "Birmingham", 30.0),
    # London, UK
    ("L1", "Canary Wharf Garage", "1 Bank St", 800, 51.50, -0.02, 25.0, "London", 80.0),
    ("L2", "King's Cross", "90 Euston Rd", 600, 51.53, -0.12, 20.0, "London", 65.0),
    # Manchester, UK
    ("M1", "Deansgate", "50 Deansgate", 400, 53.48, -2.25, 14.0, "Manchester", 40.0),
    ("M2", "Piccadilly Tower", "1 Piccadilly", 300, 53.48, -2.24, 12.0, "Manchester", 35.0),
    # New York, USA
    ("NY1", "Times Square Hub", "1 Times Sq", 1000, 40.76, -73.98, 35.0, "New York", 120.0),
    ("NY2", "Madison Ave Garage", "200 Madison Ave", 500, 40.75, -73.98, 30.0, "New York", 100.0),
    # San Francisco, USA
    ("SF1", "Financial District", "300 California St", 600, 37.79, -122.40, 28.0, "San Francisco", 90.0),
    ("SF2", "Mission Lot", "500 Mission St", 350, 37.76, -122.40, 22.0, "San Francisco", 75.0),
    # Tokyo, Japan
    ("TK1", "Shibuya Central", "2-1 Dogenzaka", 300, 35.66, 139.70, 30.0, "Tokyo", 100.0),
    ("TK2", "Shinjuku Tower", "1-1-1 Nishi-Shinjuku", 400, 35.69, 139.70, 28.0, "Tokyo", 90.0),
    # Dubai, UAE
    ("DB1", "Dubai Mall Lot", "Financial Center Rd", 1500, 25.20, 55.27, 40.0, "Dubai", 150.0),
    ("DB2", "Marina Park", "Dubai Marina", 700, 25.08, 55.14, 35.0, "Dubai", 120.0),
    # Singapore
    ("SG1", "Orchard Road", "333A Orchard Rd", 500, 1.30, 103.83, 22.0, "Singapore", 60.0),
    ("SG2", "Marina Bay", "10 Bayfront Ave", 600, 1.28, 103.86, 26.0, "Singapore", 70.0),
    # Mumbai, India
    ("MB1", "BKC Lot", "Bandra Kurla Complex", 700, 19.07, 72.87, 12.0, "Mumbai", 30.0),
    ("MB2", "Nariman Point", "1 Nariman Point", 400, 18.93, 72.82, 10.0, "Mumbai", 25.0),
    # Berlin, Germany
    ("BR1", "Potsdamer Platz", "Potsdamer Str 1", 500, 52.51, 13.37, 18.0, "Berlin", 50.0),
    ("BR2", "Alexanderplatz", "Alexanderplatz 1", 400, 52.52, 13.41, 16.0, "Berlin", 45.0),
]

def seed():
    session = get_session()

    admin = session.query(User).filter(User.email == "admin@pragma.io").first()
    if not admin:
        admin = User(
            email="admin@pragma.io",
            hashed_password=hash_password("admin123"),
            full_name="Platform Admin",
            role="admin",
            organization="Pragma Systems",
        )
        session.add(admin)
        session.flush()
        print("Created admin user: admin@pragma.io / admin123")

    owner = session.query(User).filter(User.email == "owner@pragma.io").first()
    if not owner:
        owner = User(
            email="owner@pragma.io",
            hashed_password=hash_password("owner123"),
            full_name="Jane Lotowner",
            role="lot_owner",
            organization="Downtown Parking LLC",
        )
        session.add(owner)
        session.flush()
        print("Created owner user: owner@pragma.io / owner123")

    driver = session.query(User).filter(User.email == "driver@pragma.io").first()
    if not driver:
        from src.constants import DRIVER_DEFAULT_BALANCE
        driver = User(
            email="driver@pragma.io",
            hashed_password=hash_password("driver123"),
            full_name="Default Driver",
            role="driver",
            organization="Pragma Drivers",
            balance=DRIVER_DEFAULT_BALANCE,
        )
        session.add(driver)
        session.flush()
        print("Created driver user: driver@pragma.io / driver123")

    owner_lots = {"A1", "A2", "B1", "L1", "SF1", "SG1"}

    for lot_id, name, addr, slots, lat, lng, price, city, cap in LOTS:
        existing = session.query(ParkingLot).filter(ParkingLot.lot_id == lot_id).first()
        if not existing:
            lot = ParkingLot(
                lot_id=lot_id, name=name, address=addr, city=city, total_slots=slots,
                latitude=lat, longitude=lng, base_price=price, price_cap=cap,
                owner_id=owner.id if lot_id in owner_lots else admin.id,
            )
            session.add(lot)
            session.flush()

            for days_ago in range(90):
                base = datetime.now(timezone.utc) - timedelta(days=days_ago)
                ts = base.replace(hour=random.randint(6, 22), minute=random.randint(0, 59), second=0, microsecond=0)
                occ = random.uniform(0.3, 0.95)
                flux = random.uniform(-5, 5)
                price_adj = price * (1 + (occ - 0.5) * 0.5)
                occupied = int(round(occ * slots))
                record = OccupancyRecord(
                    lot_id=lot_id, occupied_slots=occupied, total_slots=slots,
                    occupancy_rate=occ, net_flux=round(flux, 2),
                    price=round(price_adj, 2), timestamp=ts,
                )
                session.add(record)

                tx_hash = f"0x{random.getrandbits(160):040x}"
                tx = Transaction(
                    tx_hash=tx_hash, lot_id=lot_id, driver_id=f"driver_{random.randint(1,100)}",
                    action="park", amount=round(price_adj * random.uniform(0.5, 2), 2),
                    duration_minutes=random.randint(30, 240), timestamp=ts,
                )
                session.add(tx)

                rev = RevenueRecord(
                    lot_id=lot_id, date=ts.replace(hour=0, minute=0, second=0, microsecond=0),
                    total_transactions=random.randint(20, 200),
                    total_revenue=round(price_adj * random.randint(20, 200), 2),
                    avg_price=round(price_adj, 2), avg_occupancy=occ,
                )
                session.add(rev)
            print(f"Seeded lot {lot_id}: {name} ({slots} slots)")

    for lot_id in owner_lots:
        lot = session.query(ParkingLot).filter(ParkingLot.lot_id == lot_id).first()
        if lot and lot.owner_id != owner.id:
            lot.owner_id = owner.id

    session.commit()
    session.close()

    try:
        from src.api.server import _seed_micro_slots
        _seed_micro_slots()
        print("Seeded micro slots for all lots")
    except Exception as e:
        print(f"Micro slot seeding skipped: {e}")

    print("\nDatabase seeded successfully!")

if __name__ == "__main__":
    if os.environ.get("PRAGMA_ENV") == "production":
        print("Refusing to seed database in production")
        sys.exit(1)
    seed()
