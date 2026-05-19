"""Seed the Pragma database with demo data."""
import sys
import random
from datetime import datetime, timedelta
sys.path.insert(0, ".")

from src.api.database import get_session, ParkingLot, OccupancyRecord, Transaction, RevenueRecord, User
from src.api.auth import hash_password

LOTS = [
    ("A1", "Downtown Plaza", "123 Main St, Birmingham", 500, 52.48, -1.89, 15.0),
    ("A2", "Station Approach", "45 Railway Rd, Birmingham", 350, 52.47, -1.90, 12.0),
    ("B1", "Market Square", "78 Market St, Birmingham", 200, 52.48, -1.88, 10.0),
    ("B2", "University Lot", "90 Campus Dr, Birmingham", 600, 52.45, -1.93, 8.0),
    ("C1", "Hospital West", "12 Medical Rd, Birmingham", 300, 52.46, -1.92, 18.0),
    ("C2", "Shopping Center", "55 Retail Ave, Birmingham", 400, 52.49, -1.87, 14.0),
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

    for lot_id, name, addr, slots, lat, lng, price in LOTS:
        existing = session.query(ParkingLot).filter(ParkingLot.lot_id == lot_id).first()
        if not existing:
            lot = ParkingLot(
                lot_id=lot_id, name=name, address=addr, total_slots=slots,
                latitude=lat, longitude=lng, base_price=price, owner_id=admin.id,
            )
            session.add(lot)
            session.flush()

            for days_ago in range(90):
                ts = datetime.utcnow() - timedelta(days=days_ago, hours=random.randint(6, 22))
                occ = random.uniform(0.3, 0.95)
                flux = random.uniform(-5, 5)
                price_adj = price * (1 + (occ - 0.5) * 0.5)
                occupied = round(occ * slots, 1)
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

    session.commit()
    session.close()
    print("\nDatabase seeded successfully!")

if __name__ == "__main__":
    seed()
