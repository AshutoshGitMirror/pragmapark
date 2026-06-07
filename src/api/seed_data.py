"""
Extremely realistic multi-layer seed data generator.

Exercises all 6 architecture layers:
  IoT       — realistic sensor physics, noise, dropout, weather modulation
  ML        — prediction metrics with calibrated MAE, per-lot model versions
  Blockchain— transaction chain with proper hashes, ledger outbox entries
  RL        — demand-responsive pricing (price inversely correlated with occupancy)
  Digital Twin — zone-level occupancy, per-slot state transitions
  Actuator  — smart barrier events, congestion light states, slot state logs
"""

import hashlib
import json
import logging
import math
import os
import random
from datetime import datetime, timedelta, timezone, date as date_type
from typing import Optional

import numpy as np

from src.api.database import (
    ParkingLot, OccupancyRecord, Transaction, ParkingSession,
    RevenueRecord, PredictionMetric, MicroZone, MicroSlot,
    SlotStateLog, LedgerOutbox, PrebookRecord, SlotReservation,
    User, get_session,
)
from src.constants import (
    SESSION_RUNNING, SESSION_SETTLED, SESSION_CANCELLED,
    TX_COMPLETED, TX_ACTION_SESSION_FEE, TX_ACTION_PAYMENT,
    TX_ACTION_DEPOSIT, TX_ACTION_BOOKING_FEE,
    RESERVATION_ACTIVE, RESERVATION_CONFIRMED, RESERVATION_USED,
    RESERVATION_CANCELLED, OUTBOX_DELIVERED,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Seed RNG for reproducibility
# ---------------------------------------------------------------------------
_seed_rng = random.Random(42)
_np_rng = np.random.default_rng(42)

# ---------------------------------------------------------------------------
# Lot definitions — single source of truth
# Tuple: (lot_id, name, address, city, slots, lat, lng, base_price, price_cap, occ_pct)
# ---------------------------------------------------------------------------
SEED_LOTS = [
    # Birmingham — mixed commuter/retail
    ("A1", "Downtown Plaza",     "123 Main St",       "Birmingham", 500, 52.48, -1.89, 15.0, 50.0, 78.2),
    ("A2", "Station Approach",   "45 Railway Rd",     "Birmingham", 350, 52.47, -1.90, 12.0, 45.0, 65.1),
    # London — premium business + transit hub
    ("L1", "Canary Wharf Garage","1 Bank St",         "London",     800, 51.50, -0.02, 25.0, 80.0, 85.7),
    ("L2", "King's Cross",       "90 Euston Rd",      "London",     600, 51.53, -0.12, 20.0, 65.0, 71.3),
    # Mumbai — dense commercial + historic business
    ("MB1","BKC Lot",            "Bandra Kurla Complex","Mumbai",   700, 19.07, 72.87, 12.0, 30.0, 79.5),
    ("MB2","Nariman Point",      "1 Nariman Point",   "Mumbai",     400, 18.93, 72.82, 10.0, 25.0, 63.0),
]

AVG_STAY_HOURS = 2

# Fast lookup: lot_id → {base_price, price_cap, slots, city}
_SEED_LOT_MAP = {r[0]: {"base_price": r[7], "price_cap": r[8], "slots": r[4], "city": r[3]} for r in SEED_LOTS}

# Each lot's behavioural profile: (peak_amplitude, morning_peak_hour, evening_peak_hour, base_trough, weekend_factor)
# Peak amplitude: how much above trough at peak (as fraction of occ_pct)
# Some lots are commuter-heavy (twin-peak), others are leisure (single afternoon peak)
LOT_PROFILE = {
    "A1":  {"type": "mixed_retail",   "amp": 0.52, "shape": "twin", "morning_peak": 10, "evening_peak": 15, "trough": 0.50, "weekend_factor": 0.90, "covered": 0.6},
    "A2":  {"type": "commuter",       "amp": 0.60, "shape": "twin", "morning_peak": 8,  "evening_peak": 17, "trough": 0.45, "weekend_factor": 0.55, "covered": 0.3},
    "L1":  {"type": "commuter",       "amp": 0.55, "shape": "twin", "morning_peak": 9,  "evening_peak": 16, "trough": 0.42, "weekend_factor": 0.40, "covered": 0.8},
    "L2":  {"type": "transit_hub",    "amp": 0.65, "shape": "plateau", "morning_peak": 10, "evening_peak": 14, "trough": 0.40, "weekend_factor": 0.75, "covered": 0.5},
    "MB1": {"type": "commuter",       "amp": 0.58, "shape": "twin", "morning_peak": 10, "evening_peak": 17, "trough": 0.38, "weekend_factor": 0.50, "covered": 0.7},
    "MB2": {"type": "mixed_retail",   "amp": 0.48, "shape": "twin", "morning_peak": 11, "evening_peak": 16, "trough": 0.48, "weekend_factor": 0.85, "covered": 0.4},
}

# Weather model — seasonal + storm bursts
_weather_cache: dict[date_type, dict] = {}


def _weather_for(d: date_type) -> dict:
    """Deterministic weather for a date: temperature, rain probability, rain intensity."""
    if d in _weather_cache:
        return _weather_cache[d]
    # Seasonal temperature: northern-hemisphere summer peak (~day 200)
    day_of_year = d.timetuple().tm_yday
    temp_base = 15 + 12 * math.sin(2 * math.pi * (day_of_year - 100) / 365)
    # Stochastic variation per day
    rv = _seed_rng.gauss(0, 3)
    temp = round(temp_base + rv, 1)
    # Rain probability higher in winter/spring
    rain_prob = 0.15 + 0.25 * (1 + math.sin(2 * math.pi * (day_of_year - 60) / 365)) / 2
    # Storm bursts: 5% of days get heavy rain
    storm = _seed_rng.random() < 0.05
    if storm:
        rain_prob = min(1.0, rain_prob * 3)
    rain = _seed_rng.random() < rain_prob
    intensity = round(_seed_rng.uniform(0.3, 1.0), 2) if rain else 0.0
    if storm:
        intensity = round(_seed_rng.uniform(0.7, 1.5), 2)
    result = {"temp": temp, "rain": rain, "intensity": intensity, "storm": storm}
    _weather_cache[d] = result
    return result


# Event calendar — sporting events, holidays, festivals
# Each event: (month, day, affected_lot_ids, multiplier, description)
_EVENTS = [
    (5, 25, ["A1", "A2"], 1.25, "Birmingham Half Marathon"),
    (6, 15, ["A1", "A2"], 1.30, "Birmingham Pride"),
    (7, 4,  [],           1.00, "Independence Day"),        # general holiday
    (8, 12, ["A1", "A2"], 1.40, "Birmingham City FC home match"),
    (9, 1,  [],           1.00, "Labor Day"),               # general holiday
    (9, 20, ["L1", "L2"], 1.35, "London Tech Summit"),
    (10, 15, ["L1", "L2"],1.30, "London Film Festival"),
    (11, 5, ["L1", "L2"], 1.45, "London Marathon"),
    (12, 1, ["MB1","MB2"],1.35, "Mumbai International Film Festival"),
    (12, 25, [],          1.00, "Christmas"),
    (1, 26, ["MB1","MB2"],1.30, "Republic Day (Mumbai)"),
    (3, 15, ["MB1","MB2"],1.25, "Mumbai Marathon"),
]


def _event_multiplier_for(d: date_type, lot_id: str) -> float:
    """Return occupancy multiplier if an event is active for this lot+date."""
    for em, ed, lots, mult, _name in _EVENTS:
        if (d.month, d.day) == (em, ed) and (not lots or lot_id in lots):
            return mult
    return 1.0


def _occupancy_diurnal(hour: float, profile: dict) -> float:
    """
    Compute a realistic diurnal multiplier for a given hour and lot profile.
    Returns a value between 0 and 1 that modulates the base occupancy percentage.
    """
    amp = profile["amp"]
    trough = profile["trough"]
    shape = profile["shape"]

    if shape == "twin":
        # Twin-peak: morning commute + afternoon/evening
        morning = profile["morning_peak"]
        evening = profile["evening_peak"]
        # Gaussian-like peaks using sine windows
        def _gauss_window(h, center, width=3.5):
            return math.exp(-0.5 * ((h - center) / width) ** 2)
        m = _gauss_window(hour, morning, 2.5)
        e = _gauss_window(hour, evening, 3.0)
        # Midday dip
        midday_dip = 1.0 - 0.25 * math.exp(-0.5 * ((hour - 12.5) / 2.0) ** 2)
        combined = max(m, e) * midday_dip
        # Scale to trough..1
        return trough + (1 - trough) * combined

    elif shape == "plateau":
        # Single broad peak covering midday (transit hubs, tourist areas)
        peak_center = (profile["morning_peak"] + profile["evening_peak"]) / 2
        p = math.exp(-0.5 * ((hour - peak_center) / 3.5) ** 2)
        # Broader shoulder
        p2 = math.exp(-0.5 * ((hour - peak_center) / 6.0) ** 2)
        combined = max(p, p2 * 0.85)
        return trough + (1 - trough) * combined

    else:
        # Generic sine fallback
        return trough + (1 - trough) * max(0, math.sin(math.pi * (hour - 5) / 16))


# ---------------------------------------------------------------------------
# Occupancy generation — IoT layer
# ---------------------------------------------------------------------------
def _generate_occupancy(
    lot_id: str, slots: int, occ_pct: float,
    profile: dict, dt: datetime, event_mult: float,
    weather: dict, sensor_dropout_pct: float = 0.5,
) -> Optional[dict]:
    """
    Generate a single realistic occupancy reading at a given datetime.

    Returns None if the sensor is in dropout (simulates hardware failure).
    """
    hour = dt.hour
    minute = dt.minute
    dow = dt.weekday()  # 0=Mon

    # 1. Base diurnal shape
    diurnal = _occupancy_diurnal(hour + minute / 60, profile)

    # 2. Day-of-week modulation
    if dow >= 5:  # weekend
        # Saturday similar to weekday but softer; Sunday quieter
        if dow == 5:
            dow_factor = profile["weekend_factor"] + 0.10
        else:
            dow_factor = profile["weekend_factor"]
        # Weekend peak shifts later (people sleep in)
        weekend_shift = 1.5  # hours later
        shifted_hour = (hour + minute / 60 + weekend_shift) % 24
        diurnal_weekend = _occupancy_diurnal(shifted_hour, profile)
        diurnal = diurnal * (1 - dow_factor) + diurnal_weekend * dow_factor

    # 3. Holiday: reduced commuter traffic, increased leisure
    holiday = (dt.month, dt.day) in {(1, 1), (12, 25), (12, 26)}
    if holiday:
        diurnal *= 0.60 if profile["type"] == "commuter" else 0.85

    # 4. Weather modulation
    wea = weather
    if wea["rain"] and wea["intensity"] > 0:
        # Rain increases covered lot occupancy (people seek shelter)
        if profile["covered"] > 0.5:
            diurnal *= 1.0 + 0.08 * wea["intensity"]
        else:
            diurnal *= 1.0 - 0.06 * wea["intensity"]
    if wea["storm"]:
        # Storms suppress all activity temporarily
        diurnal *= 0.85

    # 5. Event multiplier
    diurnal *= event_mult

    # 6. Clamp
    diurnal = max(0.10, min(1.0, diurnal))

    # 7. Compute raw occupancy
    raw_occ = occ_pct / 100 * diurnal

    # 8. Stochastic noise: sensor jitter ~2%, plus occasional systematic error
    noise = _np_rng.normal(0, 0.02)  # 2% Gaussian sensor noise
    raw_occ += noise

    # 9. Sensor dropout simulation
    if _seed_rng.random() < sensor_dropout_pct / 100:
        return None

    # 10. Clamp and quantize
    occ_rate = max(0.01, min(0.99, raw_occ))
    occupied = int(round(occ_rate * slots))
    occ_rate = round(occupied / slots, 4)

    # 11. Net flux: vehicles arriving/departing per 30-min window
    if profile["shape"] == "twin":
        # More flux during ramp-up/down periods
        ramp_factor = abs(math.sin(math.pi * (hour + minute / 60 - 7) / 12))
        flux = round(_np_rng.normal(0, 3 * ramp_factor), 1)
    else:
        flux = round(_np_rng.normal(0, 2), 1)

    # 12. RL-inspired pricing: price = base * (0.5 + 1.5 * occupancy)
    base_price = _SEED_LOT_MAP[lot_id]["base_price"]
    occ_mult = 0.5 + 1.5 * occ_rate  # scales from 0.5x to 2.0x as lot fills
    price = round(base_price * occ_mult, 2)

    return {
        "occupied_slots": occupied,
        "total_slots": slots,
        "occupancy_rate": occ_rate,
        "net_flux": flux,
        "price": price,
    }


# ---------------------------------------------------------------------------
# Session generation — realistic driver behaviour
# ---------------------------------------------------------------------------
def _session_arrival_hour(lot_id: str, dow: int, profile: dict) -> int:
    """Generate a realistic arrival hour based on lot type and day of week."""
    r = _seed_rng.random()
    ptype = profile["type"]
    if ptype == "commuter":
        # Twin peaks: 60% arrive 7-10am, 30% arrive 1-4pm
        if r < 0.60:
            return _seed_rng.randint(7, 10)
        elif r < 0.90:
            return _seed_rng.randint(13, 16)
        else:
            return _seed_rng.randint(17, 22)
    elif ptype == "mixed_retail":
        # Spread through day, slight midday preference
        if r < 0.30:
            return _seed_rng.randint(8, 11)
        elif r < 0.70:
            return _seed_rng.randint(11, 15)
        else:
            return _seed_rng.randint(15, 20)
    elif ptype == "transit_hub":
        # Wide spread — trains run all day
        return _seed_rng.randint(6, 22)
    # fallback
    return _seed_rng.randint(8, 18)


def _session_duration(lot_id: str, profile: dict, arrival_hour: int) -> int:
    """Generate realistic session duration in minutes."""
    ptype = profile["type"]
    if ptype == "commuter":
        # Work-day: 2-4h morning, 1-3h afternoon
        if arrival_hour < 12:
            return int(_seed_rng.gauss(210, 45))  # ~3.5h
        else:
            return int(_seed_rng.gauss(120, 30))  # ~2h
    elif ptype == "mixed_retail":
        # Shopping: 1-3h
        return int(_seed_rng.gauss(120, 40))
    elif ptype == "transit_hub":
        # Train station: 30min-3h
        return int(_seed_rng.gauss(90, 45))
    return int(_seed_rng.gauss(120, 45))


def _make_session_id(lot_id: str, idx: int, day_offset: int) -> str:
    raw = f"seed-{lot_id}-d{day_offset}-s{idx}"
    return f"S{hashlib.sha256(raw.encode()).hexdigest()[:14].upper()}"


def _make_tx_hash() -> str:
    raw = f"tx-{_seed_rng.getrandbits(64)}-{datetime.now(timezone.utc).timestamp()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _make_blockchain_ref() -> str:
    raw = f"blk-{_seed_rng.getrandbits(64)}"
    return "0x" + hashlib.sha256(raw.encode()).hexdigest()[:24]


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------
def seed_all(session, days: int = 30) -> dict:
    """
    Populate the database with extremely realistic multi-layer seed data.
    Returns a report dict with counts per table.
    """
    now = datetime.now(timezone.utc)
    # Align to a clean hour boundary for reproducibility
    now = now.replace(minute=0, second=0, microsecond=0)

    # ─── Step 0: Wipe everything ───
    for table in [
        SlotStateLog, PrebookRecord, SlotReservation, PredictionMetric,
        Transaction, ParkingSession, RevenueRecord, OccupancyRecord,
        LedgerOutbox, MicroSlot, MicroZone, ParkingLot,
    ]:
        session.query(table).delete()
    session.commit()

    # ─── Step 1: Ensure seed drivers exist ───
    drivers = []
    for email, name in [
        ("driver@pragma.io", "Alice Driver"),
        ("carol@pragma.io",  "Carol Parker"),
        ("bob@pragma.io",    "Bob Singh"),
    ]:
        u = session.query(User).filter(User.email == email).first()
        if u:
            drivers.append(u)
        else:
            from src.api.auth import hash_password
            u = User(
                email=email, hashed_password=hash_password("driver123"),
                full_name=name, role="driver", balance=5000.0,
            )
            session.add(u)
            session.flush()
            drivers.append(u)
    session.commit()

    driver_emails = [d.email for d in drivers]

    # ─── Step 2: Create lots ───
    lot_map = {}  # lot_id -> {occ_pct, slots, profile, base_price, price_cap, type_keys...}
    for rec in SEED_LOTS:
        lot_id, name, address, city, slots, lat, lng, bp, pc, occ_pct = rec
        pl = ParkingLot(
            lot_id=lot_id, name=name, address=address, city=city,
            total_slots=slots, latitude=lat, longitude=lng,
            base_price=str(bp), price_cap=str(pc),
        )
        session.add(pl)
        prf = LOT_PROFILE.get(lot_id, LOT_PROFILE["A1"])
        lot_map[lot_id] = {
            "occ_pct": occ_pct, "slots": slots, "profile": prf,
            "base_price": bp, "price_cap": pc,
            "city": city, "name": name,
        }
    session.commit()

    # ─── Step 3: Micro zones + slots (Digital Twin / Actuator layer) ───
    slot_pool = {}  # lot_id -> list of (slot_id, slot_index, zone_id)
    zone_names = {
        "A1": ["North Wing", "South Terrace", "East Deck"],
        "A2": ["Main Floor", "Lower Level", "Express Zone"],
        "L1": ["Tower A", "Tower B", "Plaza Level", "Basement"],
        "L2": ["Front Lot", "Rear Yard", "Overflow"],
        "MB1": ["Airside", "Landside", "Premium Row", "General"],
        "MB2": ["West Wing", "East Wing", "Compact"],
    }
    for lot_id, info in lot_map.items():
        slots_count = info["slots"]
        znames = zone_names.get(lot_id, ["Zone A", "Zone B", "Zone C"])
        nzones = min(len(znames), max(1, slots_count // 150))
        zones = []
        for zi in range(nzones):
            z = MicroZone(
                lot_id=lot_id,
                name=znames[zi],
                description=f"{znames[zi]} — capacity ~{slots_count // nzones}",
                centroid_x=round(_seed_rng.uniform(-100, 100), 2),
                centroid_y=round(_seed_rng.uniform(-100, 100), 2),
            )
            session.add(z)
            session.flush()
            zones.append(z)

        # Create individual micro slots
        slot_list = []
        for si in range(slots_count):
            zi = si % max(1, len(zones))
            row_label = chr(65 + (si // 20) % 26)
            # Slot type distribution: 70% regular, 10% premium, 5% EV, 5% handicap, 10% covered
            slot_type_r = _seed_rng.random()
            if slot_type_r < 0.70:
                st = "regular"
                mod = 0.0
            elif slot_type_r < 0.80:
                st = "premium"
                mod = 0.15
            elif slot_type_r < 0.85:
                st = "ev"
                mod = 0.0
            elif slot_type_r < 0.90:
                st = "handicap"
                mod = 0.0
            else:
                st = "covered"
                mod = 0.05

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
            slot_list.append({"slot_id": ms.id, "slot_index": si, "zone_id": zones[zi].id})
        slot_pool[lot_id] = slot_list

    session.commit()

    # Build lookup: lot_id → {slot_index → slot_id} for SlotStateLog generation
    slot_index_to_id: dict[str, dict[int, int]] = {
        lid: {entry["slot_index"]: entry["slot_id"] for entry in entries}
        for lid, entries in slot_pool.items()
    }

    # ─── Step 4: Generate occupancy + sessions for N days ───
    occ_count = 0
    session_count = 0
    tx_count = 0
    prediction_count = 0
    state_log_count = 0
    ledger_outbox_count = 0
    prebook_count = 0
    reservation_count = 0

    # Pre-generate hourly weather for logging
    all_occupancy_rows = []

    for day_offset in range(days, -1, -1):
        day = now - timedelta(days=day_offset)
        day_date = day.date()
        dow = day.weekday()
        weather = _weather_for(day_date)
        event_mults = {}
        for lot_id in lot_map:
            event_mults[lot_id] = _event_multiplier_for(day_date, lot_id)

        # --- 4a. Occupancy every 30 minutes ---
        for minute_offset in range(0, 24 * 60, 30):
            ts = day + timedelta(minutes=minute_offset)
            hour_frac = ts.hour + ts.minute / 60

            for lot_id, info in lot_map.items():
                em = event_mults[lot_id]
                reading = _generate_occupancy(
                    lot_id, info["slots"], info["occ_pct"],
                    info["profile"], ts, em, weather,
                )
                if reading is None:
                    continue  # sensor dropout

                or_ = OccupancyRecord(
                    lot_id=lot_id,
                    occupied_slots=reading["occupied_slots"],
                    total_slots=reading["total_slots"],
                    occupancy_rate=reading["occupancy_rate"],
                    net_flux=reading["net_flux"],
                    price=reading["price"],
                    timestamp=ts,
                )
                session.add(or_)
                occ_count += 1
                all_occupancy_rows.append((lot_id, ts, reading, info))

                # Also log slot state transitions (actuator layer)
                if minute_offset % 60 == 0 and _seed_rng.random() < 0.15:
                    # Random slot transitions to simulate movement
                    slot_pool_lot = slot_pool.get(lot_id, [])
                    if slot_pool_lot:
                        rand_slot = _seed_rng.choice(slot_pool_lot)
                        # Occasional slot state change (available → occupied or vice versa)
                        prev = "available" if reading["occupancy_rate"] > 0.5 else "occupied"
                        new = "occupied" if prev == "available" else "available"
                        ssl = SlotStateLog(
                            slot_id=rand_slot["slot_id"],
                            lot_id=lot_id,
                            previous_state=prev,
                            new_state=new,
                            timestamp=ts,
                            duration_s=round(abs(_seed_rng.gauss(5400, 1800))),
                            driver_id=_seed_rng.choice(driver_emails),
                        )
                        session.add(ssl)
                        state_log_count += 1

            # Periodic flush to avoid OOM on large datasets
            if occ_count % 2000 == 0:
                session.commit()

        session.commit()
        logger.info("seed: day %d/%d — %d occupancy records", day_offset, days, occ_count)

        # --- 4b. Generate parking sessions for this day ---
        for lot_id, info in lot_map.items():
                prf = info["profile"]
                # Sessions per day per lot: proportional to size
                n_sessions = max(2, int(info["slots"] * _seed_rng.uniform(0.15, 0.35) * event_mults[lot_id]))
                for si in range(n_sessions):
                    arr_hour = _session_arrival_hour(lot_id, dow, prf)
                    arr_minute = _seed_rng.randint(0, 55)
                    arr_dt = day + timedelta(hours=arr_hour, minutes=arr_minute)
                    if arr_dt > now:
                        continue
                    duration = _session_duration(lot_id, prf, arr_hour)
                    dep_dt = arr_dt + timedelta(minutes=duration)
                    if dep_dt > now:
                        dep_dt = None
                        duration = int((now - arr_dt).total_seconds() / 60)
                        status = SESSION_RUNNING
                    else:
                        status = SESSION_SETTLED

                    sid = _make_session_id(lot_id, si, day_offset)
                    entry_price = info["base_price"]
                    duration_h = duration / 60
                    amt = round(entry_price * duration_h, 2)
                    final_price = round(entry_price * (0.8 + 0.4 * _seed_rng.random()), 2)

                    dr_email = _seed_rng.choice(driver_emails)
                    # 1-based to match MicroSlot.slot_index (seeded at created + 1)
                    slot_idx = (si + day_offset * 7) % max(1, int(info["slots"])) + 1

                    ps = ParkingSession(
                        session_id=sid,
                        lot_id=lot_id,
                        driver_id=dr_email,
                        slot=slot_idx,
                        start_time=arr_dt,
                        end_time=dep_dt,
                        duration_minutes=duration,
                        entry_price=entry_price,
                        final_price=final_price,
                        amount_charged=amt,
                        status=status,
                        blockchain_ref=_make_blockchain_ref(),
                        payment_tx=_make_tx_hash(),
                        payment_blockchain_ref=_make_blockchain_ref(),
                        payment_method=_seed_rng.choice(["card", "card", "card", "cash"]),
                    )
                    session.add(ps)
                    session.flush()
                    session_count += 1

                    # Log slot state transitions for SlotPredictor training data
                    lot_slot_map = slot_index_to_id.get(lot_id, {})
                    sid_pk = lot_slot_map.get(slot_idx)
                    if sid_pk:
                        ssl_arr = SlotStateLog(
                            slot_id=sid_pk, lot_id=lot_id,
                            previous_state="available", new_state="occupied",
                            timestamp=arr_dt,
                            duration_s=(int(duration) * 60) if duration else 0,
                            driver_id=dr_email,
                        )
                        session.add(ssl_arr)
                        state_log_count += 1
                        if status == SESSION_SETTLED and dep_dt is not None:
                            ssl_dep = SlotStateLog(
                                slot_id=sid_pk, lot_id=lot_id,
                                previous_state="occupied", new_state="available",
                                timestamp=dep_dt,
                                duration_s=0,
                                driver_id=dr_email,
                            )
                            session.add(ssl_dep)
                            state_log_count += 1

                    # --- 4c. Generate transactions for this session ---
                    # Entry deposit
                    tx1 = Transaction(
                        tx_hash=_make_tx_hash(),
                        idempotency_key=f"seed-{sid}-deposit",
                        session_id=sid,
                        lot_id=lot_id,
                        driver_id=dr_email,
                        action=TX_ACTION_DEPOSIT,
                        amount=round(entry_price * 1.0, 2),
                        duration_minutes=duration,
                        status=TX_COMPLETED,
                        timestamp=arr_dt,
                        blockchain_ref=_make_blockchain_ref(),
                    )
                    session.add(tx1)
                    tx_count += 1

                    # Session fee
                    tx2 = Transaction(
                        tx_hash=_make_tx_hash(),
                        idempotency_key=f"seed-{sid}-fee",
                        session_id=sid,
                        lot_id=lot_id,
                        driver_id=dr_email,
                        action=TX_ACTION_SESSION_FEE,
                        amount=amt,
                        duration_minutes=duration,
                        status=TX_COMPLETED if status == SESSION_SETTLED else "pending",
                        timestamp=arr_dt + timedelta(minutes=1),
                        blockchain_ref=_make_blockchain_ref(),
                    )
                    session.add(tx2)
                    tx_count += 1

                    # Payment on completion
                    if status == SESSION_SETTLED:
                        tx3 = Transaction(
                            tx_hash=_make_tx_hash(),
                            idempotency_key=f"seed-{sid}-payment",
                            session_id=sid,
                            lot_id=lot_id,
                            driver_id=dr_email,
                            action=TX_ACTION_PAYMENT,
                            amount=amt,
                            duration_minutes=duration,
                            status=TX_COMPLETED,
                            timestamp=dep_dt,
                            blockchain_ref=_make_blockchain_ref(),
                        )
                        session.add(tx3)
                        tx_count += 1

                session.commit()

        # --- 4d. Prediction metrics (ML layer) ---
        for lot_id, info in lot_map.items():
            for hour in range(6, 22, 2):
                ts = day + timedelta(hours=hour)
                if ts > now:
                    continue
                # Realistic prediction: actual = seed occupancy at that time
                # Predict with calibrated error (MAE ~0.03-0.08)
                actual_occ = info["occ_pct"] / 100 * _occupancy_diurnal(hour, info["profile"])
                actual_occ *= event_mults[lot_id]
                actual_occ = max(0.01, min(0.99, actual_occ))
                # Model prediction with error
                pred_error = _np_rng.normal(0, 0.04)
                pred_occ = max(0.01, min(0.99, actual_occ + pred_error))
                mae = round(abs(pred_occ - actual_occ), 4)

                pm = PredictionMetric(
                    lot_id=lot_id,
                    session_id=None,
                    predicted_occupancy=round(pred_occ, 4),
                    actual_occupancy=round(actual_occ, 4),
                    mae=mae,
                    model_version=_seed_rng.choice(["rf+xgb_ensemble_v2", "rf+xgb_ensemble_v3"]),
                    timestamp=ts,
                )
                session.add(pm)
                prediction_count += 1

        session.commit()

        # --- 4e. Revenue records (daily aggregation) ---
        for lot_id, info in lot_map.items():
            occ_records = [r for r in all_occupancy_rows if r[0] == lot_id and r[1].date() == day_date]
            if occ_records:
                avg_occ = round(sum(r[2]["occupancy_rate"] for r in occ_records) / len(occ_records), 4)
                total_day_rev = round(avg_occ * info["slots"] * info["base_price"] * AVG_STAY_HOURS, 2)
                # Count sessions for this lot+day
                day_sessions = session.query(ParkingSession).filter(
                    ParkingSession.lot_id == lot_id,
                    ParkingSession.start_time >= day,
                    ParkingSession.start_time < day + timedelta(days=1),
                ).count()
                avg_price = round(info["base_price"] * (1 + 0.5 * avg_occ), 2)
                rr = RevenueRecord(
                    lot_id=lot_id,
                    date=day,  # datetime, not date
                    total_transactions=day_sessions * 2,  # deposit + fee per session
                    total_revenue=total_day_rev,
                    avg_price=avg_price,
                    avg_occupancy=avg_occ * 100,
                )
                session.add(rr)

        session.commit()

        # --- 4f. Ledger outbox (blockchain layer) ---
        # Every 6h, create a ledger batch
        for batch_hour in [6, 12, 18]:
            ts = day + timedelta(hours=batch_hour)
            if ts > now:
                continue
            lo = LedgerOutbox(
                tx_hash=_make_tx_hash(),
                payload=json.dumps({
                    "batch_id": hashlib.sha256(str(ts.timestamp()).encode()).hexdigest()[:8],
                    "timestamp": ts.isoformat(),
                    "lot_count": len(lot_map),
                    "session_count": session_count,
                    "total_revenue": round(sum(
                        info["base_price"] * info["slots"] * AVG_STAY_HOURS
                        for info in lot_map.values()
                    ) * 0.02, 2),  # ~2% of theoretical daily max
                }),
                status=OUTBOX_DELIVERED,
                created_at=ts,
                processed_at=ts + timedelta(seconds=_seed_rng.randint(10, 120)),
            )
            session.add(lo)
            ledger_outbox_count += 1

    # ─── Step 5: Prebooking records (prebook/wallet layer) ───
    for lot_id, info in lot_map.items():
        slot_lot = slot_pool.get(lot_id, [])
        if not slot_lot:
            continue
        for pi in range(3):  # 3 prebookings per lot
            target_d = now + timedelta(days=_seed_rng.randint(1, 7))
            target_h = _seed_rng.randint(9, 17)
            target = target_d.replace(hour=target_h, minute=0, second=0, microsecond=0)
            slot_entry = _seed_rng.choice(slot_lot)
            pbid = f"PB-{lot_id}-{pi}-{hashlib.sha256(str(_seed_rng.random()).encode()).hexdigest()[:6]}"

            prebook = PrebookRecord(
                prebook_id=pbid,
                lot_id=lot_id,
                driver_id=_seed_rng.choice(driver_emails),
                slot_id=slot_entry["slot_id"],
                slot_index=slot_entry["slot_index"],
                ranked_order=pi + 1,
                target_time=target,
                expires_at=target + timedelta(hours=1),
                probability_given=round(_seed_rng.uniform(0.4, 0.9), 2),
                price_at_booking=info["base_price"],
                status=_seed_rng.choice([RESERVATION_ACTIVE, RESERVATION_CONFIRMED, RESERVATION_USED]),
                booking_fee=2.0,
                deposit=info["base_price"],
                deposit_refunded=1 if _seed_rng.random() < 0.4 else 0,
            )
            session.add(prebook)
            prebook_count += 1

            # Slot reservation
            sr = SlotReservation(
                slot_id=slot_entry["slot_id"],
                driver_id=prebook.driver_id,
                idempotency_key=f"seed-res-{pbid}",
                target_time=target,
                expires_at=prebook.expires_at,
                probability_given=prebook.probability_given,
                status=RESERVATION_ACTIVE,
            )
            session.add(sr)
            reservation_count += 1

    session.commit()

    # ─── Report ───
    return {
        "status": "seeded",
        "lots_created": len(lot_map),
        "occupancy_records": occ_count,
        "sessions": session_count,
        "transactions": tx_count,
        "prediction_metrics": prediction_count,
        "revenue_records": session.query(RevenueRecord).count(),
        "micro_zones": session.query(MicroZone).count(),
        "micro_slots": session.query(MicroSlot).count(),
        "slot_state_logs": state_log_count,
        "prebook_records": prebook_count,
        "slot_reservations": reservation_count,
        "ledger_outbox_entries": ledger_outbox_count,
        "weather_days": len(_weather_cache),
        "drivers": len(drivers),
    }


# Convenience entry point
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    session = get_session()
    report = seed_all(session)
    print(json.dumps(report, indent=2))
