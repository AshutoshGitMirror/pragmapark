"""Bougie Brenda — Influencer, 3 Teslas, demands premium parking."""

import os
import sys
import tempfile
import uuid
import random
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.gettempdir()}/persona_brenda.db"
os.environ["JWT_SECRET"] = "persona-secret"
os.environ["PREDICTION_MODEL_DIR"] = os.path.join(tempfile.gettempdir(), "test-models-stress")

# Seed DB
import src.api.database as _db_mod  # noqa: E402

_db_mod.DB_URL = os.environ["DATABASE_URL"]
_db_mod._engine = None
from src.api.database import (  # noqa: E402
    get_session, User, ParkingLot, MicroSlot,
)
from src.api.auth import hash_password  # noqa: E402
from src.api.database import run_migrations  # noqa: E402

run_migrations()

db = get_session()
try:
    if not db.query(User).filter(User.email == "admin@personas.io").first():
        db.add(
            User(
                email="admin@personas.io",
                hashed_password=hash_password("Admin123!"),
                full_name="Admin",
                role="admin",
            )
        )
    for info in [
        ("ut_lot_a", 200, 10.0),
        ("ut_lot_b", 500, 12.0),
        ("ut_lot_c", 100, 8.0),
    ]:
        if (
            not db.query(ParkingLot)
            .filter(ParkingLot.lot_id == info[0])
            .first()
        ):
            db.add(
                ParkingLot(
                    lot_id=info[0],
                    name=f"UT {info[0]}",
                    total_slots=info[1],
                    base_price=info[2],
                    address=f"{random.randint(1, 999)} Main St",
                    latitude=round(random.uniform(40.0, 41.0), 6),
                    longitude=round(random.uniform(-74.0, -73.0), 6),
                )
            )
    db.commit()
    for lot_id, total, _ in [
        ("ut_lot_a", 200, 10.0),
        ("ut_lot_b", 500, 12.0),
        ("ut_lot_c", 100, 8.0),
    ]:
        if db.query(MicroSlot).filter(MicroSlot.lot_id == lot_id).count() == 0:
            rows, created = max(1, math.ceil(total / 20)), 0
            per_row = math.ceil(total / rows)
            for r in range(rows):
                for p in range(per_row):
                    if created >= total:
                        break
                    st = (
                        "handicap"
                        if random.random() < 0.05
                        else ("ev" if random.random() < 0.10 else "regular")
                    )
                    db.add(
                        MicroSlot(
                            lot_id=lot_id,
                            slot_index=created + 1,
                            row_label=chr(65 + r),
                            position=p + 1,
                            slot_type=st,
                            active=1,
                            base_modifier_score=random.uniform(0, 0.5),
                        )
                    )
                    created += 1
            db.commit()
finally:
    db.close()

from fastapi.testclient import TestClient  # noqa: E402
from src.api.server import app  # noqa: E402

client = TestClient(app)

EMAIL = f"brenda_{uuid.uuid4().hex[:6]}@test.io"
PW = "Tesla4Life!"

# 1. REGISTER
r = client.post(
    "/api/v1/auth/register",
    json={
        "email": EMAIL,
        "password": PW,
        "full_name": "Bougie Brenda",
    },
)
assert r.status_code == 200, f"REGISTER: {r.text}"
print("✅ BRENDA REGISTERED. welcome, queen.")

# 2. LOGIN
r = client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PW})
assert r.status_code == 200, f"LOGIN: {r.text}"
tok = r.json()["access_token"]
h = {"Authorization": f"Bearer {tok}"}
print("✅ BRENDA LOGGED IN. 'finally.'")

# 3. BROWSE LOTS — expects premium, finds ONLY BASIC
r = client.get("/api/v1/driver/lots", headers=h)
assert r.status_code == 200
lots = r.json().get("lots", [])
print(f"🔍 BRENDA BROWSES LOTS... {len(lots)} lots.")
for lot in lots:
    print(
        f"   {lot['name']} — ₹{lot['dynamic_price']:.2f}, "
        f"{lot['available_spots']} spots, NO VALET?!"
    )
    assert "latitude" in lot, "WHERE'S THE GPS FOR MY DRIVER?"
    assert "address" in lot, "I NEED TO TELL MY DRIVER WHERE TO GO"

# 4. CHECK A SPECIFIC LOT DETAIL
r = client.get("/api/v1/driver/lots/ut_lot_a", headers=h)
d = r.json()
print(
    f"🔍 BRENDA INSPECTS LOT A: ₹{d['current_price']:.2f}/hr, "
    f"{d['available_spots']} avail"
)
assert "address" in d, "how will my chauffeur find it?"
assert "predicted_occupancy" in d, "too crowded for my tesla"

# 5. START A SESSION — needs a luxury slot
r = client.post(
    "/api/v1/sessions/start",
    json={
        "lot_id": "ut_lot_a",
        "slot": 1,
    },
    headers=h,
)
print(f"🚗 BRENDA PARKS: status={r.status_code}")
if r.status_code == 200:
    sid = r.json()["session_id"]
    print(f"   session_id={sid}, 'ok fine but it better be clean'")
    # 6. END SESSION
    r = client.post(
        "/api/v1/sessions/end", json={"session_id": sid}, headers=h
    )
    assert r.status_code == 200, f"END session: {r.text}"
    print(
        f"✅ BRENDA ENDED SESSION. charged ₹{r.json()['amount_charged']:.2f}"
    )
    # 7. CHECK HISTORY
    r = client.get("/api/v1/sessions/history", headers=h)
    assert r.status_code == 200
    hist = r.json()
    print(f"📋 BRENDA CHECKS HISTORY: {hist['total_sessions']} session(s)")
else:
    print(
        f"   BRENDA: 'THIS APP IS SO CHEAP.' status={r.status_code} {r.text}"
    )

# 8. CHECK PAYMENT
r = client.get("/api/v1/sessions/history", headers=h)
print("💰 BRENDA: 'wait, that's it? no hidden fees?'")
print(f"   response: {r.status_code}")
js = r.json()
if js["total_sessions"] > 0:
    sess = js["sessions"][0]
    print(
        f"   charged: ₹{sess['amount_charged']:.2f}, status={sess['status']}"
    )

print("\n🎬 BRENDA EXITS. '2 stars. where's the loyalty program?'")
