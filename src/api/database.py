import os
from datetime import datetime, timezone

from sqlalchemy import create_engine, Column, String, Float, DateTime, Integer, ForeignKey, Text
from sqlalchemy.orm import declarative_base, sessionmaker

DB_PATH = os.getenv("DATABASE_PATH", "sqlite:///data/pragma.db")
engine = create_engine(DB_PATH, connect_args={"check_same_thread": False})

with engine.connect() as conn:
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()

Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)

class ParkingLot(Base):
    __tablename__ = "parking_lots"
    lot_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    address = Column(Text, nullable=True)
    total_slots = Column(Integer, default=500)
    base_price = Column(Float, default=10.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class ParkingSession(Base):
    __tablename__ = "parking_sessions"
    session_id = Column(String, primary_key=True)
    lot_id = Column(String, ForeignKey("parking_lots.lot_id"), nullable=False)
    driver_id = Column(String, nullable=False)
    start_time = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    end_time = Column(DateTime, nullable=True)
    price_at_entry = Column(Float, default=10.0)
    amount_charged = Column(Float, nullable=True)
    blockchain_ref = Column(String, nullable=True)
    layers_activated = Column(String, nullable=True)

class Driver(Base):
    __tablename__ = "drivers"
    driver_id = Column(String, primary_key=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="driver")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class PredictionMetric(Base):
    __tablename__ = "prediction_metrics"
    id = Column(Integer, primary_key=True, autoincrement=True)
    lot_id = Column(String, nullable=False)
    driver_id = Column(String, nullable=False)
    predicted_occupancy = Column(Float, nullable=False)
    actual_occupancy = Column(Float, nullable=True)
    model_version = Column(String, default="rf+xgb+ridge")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    session_id = Column(String, ForeignKey("parking_sessions.session_id"), nullable=True)

def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class SessionManager:
    @staticmethod
    def create_session(db, session_id, lot_id, driver_id, start_time, price_at_entry,
                       blockchain_ref, layers_activated, **kw):
        from src.api.database import ParkingSession
        try:
            st = datetime.fromisoformat(start_time)
        except (ValueError, TypeError):
            st = datetime.now(timezone.utc)
        s = ParkingSession(
            session_id=session_id, lot_id=lot_id, driver_id=driver_id,
            start_time=st, price_at_entry=price_at_entry,
            blockchain_ref=blockchain_ref,
            layers_activated=",".join(layers_activated) if isinstance(layers_activated, list) else layers_activated,
        )
        db.add(s)
        db.commit()

    @staticmethod
    def end_session(db, session_id, end_time, amount_charged, **kw):
        from src.api.database import ParkingSession
        s = db.query(ParkingSession).filter(ParkingSession.session_id == session_id).first()
        if s:
            try:
                s.end_time = datetime.fromisoformat(end_time)
            except (ValueError, TypeError):
                s.end_time = datetime.now(timezone.utc)
            s.amount_charged = amount_charged
            db.commit()

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print(f"Database created at {DB_PATH}")
