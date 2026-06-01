import os
import threading
import logging
from datetime import datetime, timezone
from sqlalchemy import create_engine, Engine, Column, Integer, String, Float, Numeric, DateTime, ForeignKey, UniqueConstraint, event, text, Text, inspect as sa_inspect
from sqlalchemy.orm import DeclarativeBase, sessionmaker, relationship
from src.constants import SESSION_RUNNING, TX_COMPLETED, TX_ACTION_SESSION_FEE, RESERVATION_ACTIVE, OUTBOX_PENDING

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_URL = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(os.path.dirname(BASE_DIR), '..', 'data', 'pragma.db')}")
_engine = None
_Session = None
_session_lock = threading.Lock()


class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(String(50), default="driver")
    organization = Column(String(255))
    balance = Column(Float, default=0.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    lots = relationship("ParkingLot", back_populates="owner")

class ParkingLot(Base):
    __tablename__ = "parking_lots"
    id = Column(Integer, primary_key=True)
    lot_id = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    address = Column(String(500))
    city = Column(String(100), default="")
    total_slots = Column(Integer, nullable=False)
    latitude = Column(Float)
    longitude = Column(Float)
    timezone = Column(String(50), default="UTC")
    base_price = Column(Numeric(10, 2), default=10.0)
    price_cap = Column(Numeric(10, 2), default=200.0)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    owner = relationship("User", back_populates="lots")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class OccupancyRecord(Base):
    __tablename__ = "occupancy_records"
    id = Column(Integer, primary_key=True)
    lot_id = Column(String(50), ForeignKey("parking_lots.lot_id", ondelete="CASCADE"), nullable=False, index=True)
    occupied_slots = Column(Integer, nullable=False)
    total_slots = Column(Integer, nullable=False)
    occupancy_rate = Column(Float, nullable=False)
    net_flux = Column(Float, default=0.0)
    price = Column(Numeric(10, 2), default=10.0)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True)
    tx_hash = Column(String(100), unique=True, nullable=False)
    idempotency_key = Column(String(64), unique=True, nullable=True, index=True)
    session_id = Column(String(100), ForeignKey("parking_sessions.session_id", ondelete="SET NULL"), index=True)
    lot_id = Column(String(50), ForeignKey("parking_lots.lot_id", ondelete="CASCADE"), nullable=False, index=True)
    driver_id = Column(String(100), nullable=False, index=True)
    action = Column(String(50), default=TX_ACTION_SESSION_FEE, nullable=False, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    duration_minutes = Column(Integer)
    status = Column(String(20), default=TX_COMPLETED, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    blockchain_ref = Column(String(255))

class ParkingSession(Base):
    __tablename__ = "parking_sessions"
    id = Column(Integer, primary_key=True)
    session_id = Column(String(100), unique=True, index=True, nullable=False)
    lot_id = Column(String(50), ForeignKey("parking_lots.lot_id", ondelete="CASCADE"), nullable=False, index=True)
    driver_id = Column(String(100), nullable=False, index=True)
    slot = Column(Integer, default=0)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=True)
    duration_minutes = Column(Integer, default=0)
    entry_price = Column(Numeric(10, 2), default=10.0)
    final_price = Column(Numeric(10, 2), default=10.0)
    amount_charged = Column(Numeric(10, 2), default=0.0)
    status = Column(String(20), default=SESSION_RUNNING, index=True)
    blockchain_ref = Column(String(255))
    payment_tx = Column(String(255))
    payment_blockchain_ref = Column(String(255))
    payment_method = Column(String(20), default="card")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class PredictionMetric(Base):
    __tablename__ = "prediction_metrics"
    id = Column(Integer, primary_key=True)
    lot_id = Column(String(50), ForeignKey("parking_lots.lot_id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String(100), ForeignKey("parking_sessions.session_id", ondelete="CASCADE"), index=True)
    predicted_occupancy = Column(Float, nullable=False)
    actual_occupancy = Column(Float, nullable=True)
    mae = Column(Float, nullable=True)
    model_version = Column(String(50), default="rf+xgb_ensemble_v2")
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

class TokenBlacklist(Base):
    __tablename__ = "token_blacklist"
    id = Column(Integer, primary_key=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    revoked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime, nullable=False)


class LedgerOutbox(Base):
    __tablename__ = "ledger_outbox"
    id = Column(Integer, primary_key=True)
    tx_hash = Column(String(64), unique=True, nullable=False, index=True)
    payload = Column(Text, nullable=False)
    status = Column(String(20), default=OUTBOX_PENDING, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    processed_at = Column(DateTime, nullable=True)

class MicroZone(Base):
    __tablename__ = "micro_zones"
    id = Column(Integer, primary_key=True)
    lot_id = Column(String(50), ForeignKey("parking_lots.lot_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, default="")
    centroid_x = Column(Float, default=0.0)
    centroid_y = Column(Float, default=0.0)

class MicroSlot(Base):
    __tablename__ = "micro_slots"
    id = Column(Integer, primary_key=True)
    lot_id = Column(String(50), ForeignKey("parking_lots.lot_id", ondelete="CASCADE"), nullable=False, index=True)
    slot_index = Column(Integer, nullable=False)
    micro_zone_id = Column(Integer, ForeignKey("micro_zones.id", ondelete="SET NULL"), nullable=True, index=True)
    row_label = Column(String(10), default="A")
    position = Column(Integer, default=0)
    slot_type = Column(String(20), default="regular")
    active = Column(Integer, default=1)
    base_modifier_score = Column(Float, default=0.0)
    current_modifier = Column(Float, default=0.0)
    __table_args__ = (UniqueConstraint("lot_id", "slot_index", name="uq_slot_lot_index"),)

class SlotReservation(Base):
    __tablename__ = "slot_reservations"
    id = Column(Integer, primary_key=True)
    slot_id = Column(Integer, ForeignKey("micro_slots.id", ondelete="CASCADE"), nullable=False, index=True)
    driver_id = Column(String(100), nullable=False, index=True)
    idempotency_key = Column(String(64), nullable=True, index=True)
    target_time = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    probability_given = Column(Float, default=0.0)
    status = Column(String(20), default=RESERVATION_ACTIVE, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    # NOTE: SQLite doesn't enforce uniqueness on nullable columns well, so idempotency
    # uniqueness is enforced at the application layer in reserve_slot.

class PrebookRecord(Base):
    __tablename__ = "prebook_records"
    id = Column(Integer, primary_key=True)
    prebook_id = Column(String(64), unique=True, nullable=False, index=True)
    lot_id = Column(String(50), ForeignKey("parking_lots.lot_id", ondelete="CASCADE"), nullable=False, index=True)
    driver_id = Column(String(100), nullable=False, index=True)
    slot_id = Column(Integer, ForeignKey("micro_slots.id", ondelete="CASCADE"), nullable=False)
    slot_index = Column(Integer, nullable=False)
    ranked_order = Column(Integer, default=0)
    target_time = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    probability_given = Column(Float, default=0.0)
    price_at_booking = Column(Numeric(10, 2), default=0.0)
    status = Column(String(20), default=RESERVATION_ACTIVE, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    # Wallet deduction fields (Option D)
    booking_fee = Column(Float, default=0.0)
    deposit = Column(Float, default=0.0)
    deposit_refunded = Column(Integer, default=0)

class RevenueRecord(Base):
    __tablename__ = "revenue_records"
    id = Column(Integer, primary_key=True)
    lot_id = Column(String(50), ForeignKey("parking_lots.lot_id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(DateTime, nullable=False, index=True)
    total_transactions = Column(Integer, default=0, nullable=False)
    total_revenue = Column(Numeric(10, 2), default=0.0, nullable=False)
    avg_price = Column(Numeric(10, 2), default=0.0, nullable=False)
    avg_occupancy = Column(Float, default=0.0, nullable=False)

    __table_args__ = (UniqueConstraint("lot_id", "date", name="uq_revenue_lot_date"),)

class SlotStateLog(Base):
    __tablename__ = "slot_state_log"
    id = Column(Integer, primary_key=True)
    slot_id = Column(Integer, nullable=False, index=True)
    lot_id = Column(String(20), nullable=False, index=True)
    previous_state = Column(String(20), nullable=True)
    new_state = Column(String(20), nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    duration_s = Column(Float, default=0.0)
    driver_id = Column(String(100), nullable=True)


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if DB_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def _enable_wal(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA synchronous=NORMAL")
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
        event.listen(_engine, "connect", _enable_wal)
    else:
        _engine = create_engine(DB_URL, echo=False)
    Base.metadata.create_all(_engine)
    return _engine


def get_session():
    global _Session
    if _Session is None:
        with _session_lock:
            if _Session is None:
                _Session = sessionmaker(bind=get_engine())
    return _Session()


def get_db():
    db = get_session()
    try:
        yield db
    finally:
        db.close()


class get_db_cm:
    """Context manager for `with` blocks. Same as get_db() but compatible with both `with` and Depends()."""
    def __enter__(self):
        self._db = get_session()
        return self._db
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self._db.rollback()
        self._db.close()
        return False


def run_migrations():
    try:
        from alembic.config import Config
        from alembic import command
        alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini"))
        alembic_cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "..", "alembic"))
        if DB_URL:
            alembic_cfg.set_main_option("sqlalchemy.url", DB_URL)
        command.upgrade(alembic_cfg, "head")
        logging.getLogger(__name__).info("event=migrations.applied")
    except Exception as e:
        logging.getLogger(__name__).warning("event=migrations.fallback_to_create_all error=%s", e)
        Base.metadata.create_all(get_engine())
    engine = get_engine()
    inspector = sa_inspect(engine)
    existing_tables = inspector.get_table_names()

    if "parking_sessions" in existing_tables:
        cols = [c["name"] for c in inspector.get_columns("parking_sessions")]
        if "payment_method" not in cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE parking_sessions ADD COLUMN payment_method VARCHAR(20) DEFAULT 'card'"))
                conn.commit()
                logging.getLogger(__name__).info("Added payment_method column to parking_sessions")

    if "users" in existing_tables:
        cols = [c["name"] for c in inspector.get_columns("users")]
        if "balance" not in cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN balance FLOAT DEFAULT 0.0"))
                conn.commit()
                logging.getLogger(__name__).info("Added balance column to users")

    if "prebook_records" in existing_tables:
        cols = [c["name"] for c in inspector.get_columns("prebook_records")]
        for col_name, col_def in [
            ("booking_fee", "FLOAT DEFAULT 0.0"),
            ("deposit", "FLOAT DEFAULT 0.0"),
            ("deposit_refunded", "INTEGER DEFAULT 0"),
        ]:
            if col_name not in cols:
                with engine.connect() as conn:
                    conn.execute(text(f"ALTER TABLE prebook_records ADD COLUMN {col_name} {col_def}"))
                    conn.commit()
                    logging.getLogger(__name__).info("Added %s column to prebook_records", col_name)
