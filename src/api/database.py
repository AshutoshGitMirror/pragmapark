import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, Engine, Column, Integer, String, Float, DateTime, ForeignKey, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker, relationship

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_URL = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(os.path.dirname(BASE_DIR), '..', 'data', 'pragma.db')}")
_engine = None
_Session = None


class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(String(50), default="lot_owner")
    organization = Column(String(255))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    lots = relationship("ParkingLot", back_populates="owner", cascade="all, delete-orphan")

class ParkingLot(Base):
    __tablename__ = "parking_lots"
    id = Column(Integer, primary_key=True)
    lot_id = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    address = Column(String(500))
    total_slots = Column(Integer, nullable=False)
    latitude = Column(Float)
    longitude = Column(Float)
    timezone = Column(String(50), default="UTC")
    base_price = Column(Float, default=10.0)
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="lots")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class OccupancyRecord(Base):
    __tablename__ = "occupancy_records"
    id = Column(Integer, primary_key=True)
    lot_id = Column(String(50), ForeignKey("parking_lots.lot_id"), index=True)
    occupied_slots = Column(Integer, nullable=False)
    total_slots = Column(Integer, nullable=False)
    occupancy_rate = Column(Float, nullable=False)
    net_flux = Column(Float, default=0.0)
    price = Column(Float, default=10.0)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True)
    tx_hash = Column(String(100), unique=True)
    lot_id = Column(String(50), ForeignKey("parking_lots.lot_id"), index=True)
    driver_id = Column(String(100))
    action = Column(String(50))
    amount = Column(Float)
    duration_minutes = Column(Integer)
    status = Column(String(20), default="completed")
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class ParkingSession(Base):
    __tablename__ = "parking_sessions"
    id = Column(Integer, primary_key=True)
    session_id = Column(String(100), unique=True, index=True, nullable=False)
    lot_id = Column(String(50), ForeignKey("parking_lots.lot_id"), index=True, nullable=False)
    driver_id = Column(String(100), nullable=False)
    slot = Column(Integer, default=0)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    duration_minutes = Column(Integer, default=0)
    entry_price = Column(Float, default=10.0)
    final_price = Column(Float, default=10.0)
    amount_charged = Column(Float, default=0.0)
    status = Column(String(20), default="active")
    blockchain_ref = Column(String(255))
    payment_tx = Column(String(255))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class PredictionMetric(Base):
    __tablename__ = "prediction_metrics"
    id = Column(Integer, primary_key=True)
    lot_id = Column(String(50), ForeignKey("parking_lots.lot_id"), index=True)
    session_id = Column(String(100), ForeignKey("parking_sessions.session_id"), index=True)
    predicted_occupancy = Column(Float, nullable=False)
    actual_occupancy = Column(Float, nullable=True)
    mae = Column(Float, nullable=True)
    model_version = Column(String(50), default="rf+xgb_ensemble_v2")
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class RevenueRecord(Base):
    __tablename__ = "revenue_records"
    id = Column(Integer, primary_key=True)
    lot_id = Column(String(50), ForeignKey("parking_lots.lot_id"), index=True)
    date = Column(DateTime, index=True)
    total_transactions = Column(Integer, default=0)
    total_revenue = Column(Float, default=0.0)
    avg_price = Column(Float, default=0.0)
    avg_occupancy = Column(Float, default=0.0)


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_engine():
    global _engine
    if _engine is not None:
        return _engine
    if DB_URL.startswith("sqlite"):
        db_path = DB_URL.replace("sqlite:///", "")
        dir_path = os.path.dirname(db_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        _engine = create_engine(DB_URL, echo=False, connect_args={"check_same_thread": False})
    else:
        _engine = create_engine(DB_URL, echo=False)
    Base.metadata.create_all(_engine)
    return _engine


def get_session():
    global _Session
    if _Session is None:
        _Session = sessionmaker(bind=get_engine())
    return _Session()


def init_db():
    get_engine()
