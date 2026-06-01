#!/usr/bin/env python3
"""Generate 30 days of rich historical data: occupancy, sessions, revenue.

Run on first boot or when PRAGMA_FORCE_RESEED=true.
Replaces the inline seed logic in _seed_startup().
"""
import os
import sys
import random
import uuid
import hashlib
import logging
from datetime import datetime, timedelta, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("generate_history")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.constants import is_holiday, HISTORY_DAYS

# Occupancy profiles (same as generate_slot_history.py but used for occupancy records)
WEEKDAY_OCC = {
    0: (0.03, 0.10), 1: (0.02, 0.08), 2: (0.02, 0.06), 3: (0.02, 0.05),
    4: (0.03, 0.08), 5: (0.05, 0.15), 6: (0.10, 0.30), 7: (0.25, 0.55),
    8: (0.55, 0.85), 9: (0.65, 0.90), 10: (0.70, 0.92), 11: (0.68, 0.88),
    12: (0.55, 0.80), 13: (0.50, 0.75), 14: (0.55, 0.80), 15: (0.60, 0.85),
    16: (0.65, 0.90), 17: (0.70, 0.95), 18: (0.50, 0.75), 19: (0.35, 0.60),
    20: (0.20, 0.45), 21: (0.12, 0.30), 22: (0.08, 0.20), 23: (0.05, 0.12),
}

WEEKEND_OCC = {
    0: (0.05, 0.15), 1: (0.04, 0.12), 2: (0.03, 0.10), 3: (0.03, 0.08),
    4: (0.04, 0.10), 5: (0.05, 0.12), 6: (0.08, 0.20), 7: (0.12, 0.30),
    8: (0.20, 0.45), 9: (0.30, 0.55), 10: (0.40, 0.65), 11: (0.50, 0.75),
    12: (0.55, 0.80), 13: (0.55, 0.78), 14: (0.50, 0.75), 15: (0.45, 0.70),
    16: (0.40, 0.65), 17: (0.35, 0.55), 18: (0.30, 0.50), 19: (0.25, 0.45),
    20: (0.18, 0.35), 21: (0.12, 0.25), 22: (0.08, 0.18), 23: (0.06, 0.12),
}

HOLIDAY_OCC = {
    0: (0.08, 0.18), 1: (0.06, 0.14), 2: (0.05, 0.12), 3: (0.04, 0.10),
    4: (0.05, 0.12), 5: (0.06, 0.14), 6: (0.10, 0.22), 7: (0.15, 0.32),
    8: (0.22, 0.48), 9: (0.32, 0.58), 10: (0.42, 0.68), 11: (0.52, 0.76),
    12: (0.58, 0.82), 13: (0.55, 0.80), 14: (0.52, 0.76), 15: (0.48, 0.72),
    16: (0.42, 0.68), 17: (0.38, 0.58), 18: (0.32, 0.52), 19: (0.28, 0.48),
    20: (0.20, 0.38), 21: (0.14, 0.28), 22: (0.10, 0.20), 23: (0.08, 0.15),
}


def _get_occ_profile(dt: datetime) -> dict:
    if is_holiday(dt):
        return HOLIDAY_OCC
    if dt.weekday() >= 5:
        return WEEKEND_OCC
    return WEEKDAY_OCC


def seed_history(num_days: int | None = None):
    if num_days is None:
        num_days = int(os.getenv("PRAGMA_HISTORY_DAYS", str(HISTORY_DAYS)))

    import random as _rand
    _rand.seed(42)  # Reproducible

    from src.api.database import (
        get_db_cm, ParkingLot, OccupancyRecord, Transaction,
        RevenueRecord, ParkingSession, PredictionMetric,
    )
    from src.constants import TX_ACTION_SESSION_FEE, SESSION_RUNNING

    with get_db_cm() as db:
        lots = db.query(ParkingLot).all()
        if not lots:
            log.warning("No lots found — skipping history generation")
            return

        now = datetime.now(timezone.utc)
        total_records = 0

        for lot in lots:
            bp = float(lot.base_price)
            ts = lot.total_slots
            lid = lot.lot_id

            # Clear existing history for this lot
            db.query(PredictionMetric).filter(PredictionMetric.lot_id == lid).delete()
            db.query(ParkingSession).filter(ParkingSession.lot_id == lid).delete()
            db.query(RevenueRecord).filter(RevenueRecord.lot_id == lid).delete()
            db.query(Transaction).filter(Transaction.lot_id == lid).delete()
            db.query(OccupancyRecord).filter(OccupancyRecord.lot_id == lid).delete()
            db.flush()

            lot_records = 0
            for days_ago in range(num_days):
                d = now - timedelta(days=days_ago)
                daily_key = d.replace(hour=0, minute=0, second=0, microsecond=0)
                profile = _get_occ_profile(d)

                day_occ_sum = 0.0
                day_tx_count = 0

                for h in range(6, 23, 2):  # Every 2 hours from 6-22
                    occ_min, occ_max = profile.get(h, (0.1, 0.5))
                    occ = random.uniform(occ_min, occ_max) * random.uniform(0.85, 1.15)
                    occ = max(0.02, min(0.98, occ))

                    ts_record = d.replace(hour=h, minute=random.randint(0, 59), second=0, microsecond=0)
                    flux = random.uniform(-8, 8)
                    price_adj = round(bp * (1 + (occ - 0.5) * 0.6), 2)
                    occupied = int(round(occ * ts))

                    db.add(OccupancyRecord(
                        lot_id=lid, occupied_slots=occupied, total_slots=ts,
                        occupancy_rate=round(occ, 3), net_flux=round(flux, 2),
                        price=price_adj, timestamp=ts_record,
                    ))
                    db.add(Transaction(
                        tx_hash=f"0x{uuid.uuid4().hex}", lot_id=lid,
                        driver_id=f"driver_{random.randint(1, 200)}",
                        action=TX_ACTION_SESSION_FEE,
                        amount=round(price_adj * random.uniform(0.5, 2.5), 2),
                        duration_minutes=random.randint(30, 240),
                        timestamp=ts_record,
                    ))
                    day_occ_sum += occ
                    day_tx_count += 1
                    lot_records += 1

                # Daily revenue aggregate
                if day_tx_count > 0:
                    day_avg_occ = round(day_occ_sum / day_tx_count, 3)
                    day_avg_price = round(bp * (1 + (day_avg_occ - 0.5) * 0.6), 2)
                    tx_count = random.randint(30, 300)
                    db.add(RevenueRecord(
                        lot_id=lid, date=daily_key,
                        total_transactions=tx_count,
                        total_revenue=round(day_avg_price * tx_count, 2),
                        avg_price=day_avg_price,
                        avg_occupancy=day_avg_occ,
                    ))
                    lot_records += 1

            log.info("Generated %d records for lot %s", lot_records, lid)

        db.commit()

        # Create 20 active parking sessions
        lot_ids = [l.lot_id for l in lots]
        from src.api.database import User
        driver_emails = [f"driver{d}@demo.io" for d in range(1, 6)]

        for i in range(20):
            lid = random.choice(lot_ids)
            driver_email = driver_emails[i % len(driver_emails)]
            slot_num = random.randint(1, 20)
            start_offset = random.randint(10, 180)
            start = now - timedelta(minutes=start_offset)
            entry_price = float(db.query(ParkingLot.base_price).filter(ParkingLot.lot_id == lid).scalar() or 10)
            sid = hashlib.sha256(os.urandom(32)).hexdigest()[:16]
            db.add(ParkingSession(
                session_id=sid, lot_id=lid, driver_id=driver_email,
                slot=slot_num, start_time=start, entry_price=entry_price,
                status=SESSION_RUNNING, payment_method=random.choice(["card", "wallet"]),
            ))
            db.add(PredictionMetric(
                lot_id=lid, session_id=sid,
                predicted_occupancy=round(random.uniform(0.3, 0.9), 3),
                model_version="rf+xgb_ensemble_v2",
            ))
        db.commit()
        log.info("Created 20 active parking sessions")

        # Set driver balances
        from src.constants import DRIVER_DEFAULT_BALANCE
        for email in driver_emails:
            u = db.query(User).filter(User.email == email).first()
            if u and (u.balance is None or u.balance == 0.0):
                u.balance = DRIVER_DEFAULT_BALANCE
        db.commit()
        log.info("Set driver balances to %.0f", DRIVER_DEFAULT_BALANCE)

        log.info("History generation complete: %d days, %d lots", num_days, len(lots))


if __name__ == "__main__":
    seed_history()
