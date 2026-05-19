import os, sys
sys.path.insert(0, os.getcwd())

from src.api.database import engine, Base, ParkingLot
from src.api.database import SessionLocal

Base.metadata.create_all(bind=engine)
db = SessionLocal()

lots = [
    ParkingLot(lot_id="lot_central", name="Central Parking",
               address="100 Main St", total_slots=500, base_price=12.0),
    ParkingLot(lot_id="lot_north", name="North Side Garage",
               address="200 North Ave", total_slots=300, base_price=8.0),
    ParkingLot(lot_id="lot_south", name="South Park Plaza",
               address="300 South Blvd", total_slots=400, base_price=10.0),
]
for lot in lots:
    db.merge(lot)
db.commit()
db.close()
print("Seeded 3 parking lots")
