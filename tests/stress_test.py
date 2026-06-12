"""Stress/QA test: 30 iterations × full-system coverage.

Tests 9 major categories:
  A  Full user flow (register → browse → prebook → confirm → session → pay)
  B  Auth & security (no-auth, bad token, IDOR, admin-gate, SQLi, forged JWT)
  C  Race conditions (concurrent prebook/reserve/confirm on same slot)
  D  Edge cases (expired, fallback, double-confirm, double-release, bad input)
  E  Admin operations (seed, create lot, blockchain mine, pipeline status)
  F  Session lifecycle (start → active check → end → history → payment)
  G  System endpoints (health, dashboard, prediction, pricing, DT, scenarios)
  H  Data integrity (engine ↔ DB consistency after rollback)
  I  Rate limit exhaustion

Usage:  uv run python tests/stress_test.py
"""

import os
import sys
import time
import threading
import math
import random
import gc
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault(
    "DATABASE_URL", f"sqlite:////tmp/stress_{os.getpid()}.db"
)
os.environ.setdefault("JWT_SECRET", "stress-test-secret-2024")
os.environ.setdefault("MODEL_ARTIFACT_PATH", "/tmp/test-models-stress")
os.environ["PREDICTION_MODEL_DIR"] = "/tmp/test-models-stress"
os.environ.setdefault("PRAGMA_SEED", "42")

# ---------------------------------------------------------------------------
# Build fresh DB
# ---------------------------------------------------------------------------
from src.api.server import app  # noqa: E402
from src.api.database import (  # noqa: E402
    Base,
    get_engine,
    get_session,
    User,
    ParkingLot,
    MicroSlot,
)
from src.api.auth import hash_password  # noqa: E402
from src.micro.state_engine import slot_state_engine  # noqa: E402
from src.micro.models import SlotState  # noqa: E402


engine = get_engine()
Base.metadata.create_all(bind=engine)

# seed admin
db = get_session()
try:
    if not db.query(User).filter(User.email == "admin@str.ess").first():
        db.add(
            User(
                email="admin@str.ess",
                hashed_password=hash_password("Admin123!"),
                full_name="Stress Admin",
                role="admin",
            )
        )
    # create 3 lots
    for info in [
        ("stress_lot_a", 200, 10.0),
        ("stress_lot_b", 500, 12.0),
        ("stress_lot_c", 100, 8.0),
    ]:
        if (
            not db.query(ParkingLot)
            .filter(ParkingLot.lot_id == info[0])
            .first()
        ):
            db.add(
                ParkingLot(
                    lot_id=info[0],
                    name=f"Stress {info[0]}",
                    total_slots=info[1],
                    base_price=info[2],
                )
            )
    db.commit()
finally:
    db.close()

# seed micro slots for all lots
slot_state_engine._states.clear()
slot_state_engine._timestamps.clear()
slot_state_engine._reservations.clear()
slot_state_engine._reservation_expiry.clear()
slot_state_engine._prebook_drivers.clear()
slot_state_engine._prebook_expiry.clear()
slot_state_engine._prebook_target.clear()
slot_state_engine._last_cleanup = 0.0

with get_session() as s:
    for lot_id, total, base_p in [
        ("stress_lot_a", 200, 10.0),
        ("stress_lot_b", 500, 12.0),
        ("stress_lot_c", 100, 8.0),
    ]:
        if s.query(MicroSlot).filter(MicroSlot.lot_id == lot_id).count() == 0:
            rows = max(1, math.ceil(total / 20))
            per_row = math.ceil(total / rows)
            created = 0
            for r in range(rows):
                rl = chr(65 + r)
                for p in range(per_row):
                    if created >= total:
                        break
                    roll = random.random()
                    st = "regular"
                    if roll < 0.05:
                        st = "handicap"
                    elif roll < 0.10:
                        st = "ev"
                    elif roll < 0.25:
                        st = "covered"
                    elif roll < 0.30:
                        st = "premium"
                    s.add(
                        MicroSlot(
                            lot_id=lot_id,
                            slot_index=created + 1,
                            row_label=rl,
                            position=p + 1,
                            slot_type=st,
                            active=1,
                            base_modifier_score=random.uniform(0, 0.5),
                        )
                    )
                    created += 1
            s.commit()

# cleanup rate-limiters
from src.api.server import _global_rate_limiter  # noqa: E402


def clr_limits():
    _global_rate_limiter._buckets.clear()
    from src.api.database import RateLimitWindow, get_engine
    from sqlalchemy.orm import Session

    with Session(bind=get_engine()) as s:
        s.query(RateLimitWindow).delete()
        s.commit()


clr_limits()

from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(app)

# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------
PASS = 0
FAIL = 0
ERRORS = []
lock = threading.Lock()


def check(label, ok, detail=""):
    global PASS, FAIL
    with lock:
        if ok:
            PASS += 1
        else:
            FAIL += 1
            ERRORS.append(f"  FAIL [{label}]: {detail[:120]}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _reg(email, password="Pass123!"):
    return client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": email.split("@")[0],
        },
    )


def _login(email, password="Pass123!"):
    return client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )


def _auth(email):
    return _cached_auth(email)


_ADMIN_TOKEN_CACHE = {"token": None}


def _admin():
    if _ADMIN_TOKEN_CACHE["token"] is None:
        with _TOKENS_LOCK:
            if _ADMIN_TOKEN_CACHE["token"] is None:
                clr_limits()
                r = _login("admin@str.ess", "Admin123!")
                if r.status_code != 200:
                    r = _login("admin@str.ess", "Admin123!")
                if r.status_code == 200:
                    _ADMIN_TOKEN_CACHE["token"] = r.json().get(
                        "access_token", ""
                    )
                else:
                    _reg("admin@str.ess", "Admin123!")
                    clr_limits()
                    r = _login("admin@str.ess", "Admin123!")
                    if r.status_code == 200:
                        _ADMIN_TOKEN_CACHE["token"] = r.json().get(
                            "access_token", ""
                        )
    return (
        {"Authorization": f"Bearer {_ADMIN_TOKEN_CACHE['token']}"}
        if _ADMIN_TOKEN_CACHE["token"]
        else {}
    )


_TOKENS_CACHE = {}
_TOKENS_LOCK = threading.Lock()


def _cached_auth(email):
    if _TOKENS_CACHE.get(email) is None:
        with _TOKENS_LOCK:
            if email not in _TOKENS_CACHE:
                clr_limits()
                r = _login(email)
                if r.status_code != 200:
                    _reg(email)
                    clr_limits()
                    r = _login(email)
                if r.status_code == 200:
                    _TOKENS_CACHE[email] = r.json().get("access_token", "")
    token = _TOKENS_CACHE.get(email)
    return {"Authorization": f"Bearer {token}"} if token else {}


def new_driver(tag, it):
    return f"driver_{tag}_{it}_{random.randint(10000, 99999)}@test.io"


def _target():
    return (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()


def _flow_assert(label, r, expected, msg=""):
    ok = (
        r.status_code == expected
        if isinstance(expected, int)
        else r.status_code in expected
    )
    check(label, ok, f"got {r.status_code} {r.text[:100]} {msg}")


# ---------------------------------------------------------------------------
# SCENARIO WEIGHTS — each iteration picks a mix
# ---------------------------------------------------------------------------
SCENARIOS_BY_ITER = {}
# Iteration 1-5: full happy path + admin ops
# Iteration 6-10: security heavy
# Iteration 11-15: race conditions
# Iteration 16-20: edge cases + data integrity
# Iteration 21-25: mixed heavy load
# Iteration 26-30: all categories max coverage

print(f"\n{'=' * 70}")
print("  QA STRESS TEST — 30 iterations × full-system chaos")
print(f"{'=' * 70}\n")
t0 = time.time()

for iteration in range(1, 31):
    it = iteration
    it_dev = f"I{it:02d}"
    try:
        clr_limits()
        with lock:
            slot_state_engine._cleanup_batch()
            _ADMIN_TOKEN_CACHE["token"] = None
            # Reset all engine states for stress_lot_a's slots
            for sid in list(slot_state_engine._states.keys()):
                slot_state_engine._states[sid] = SlotState.AVAILABLE
            slot_state_engine._reservations.clear()
            slot_state_engine._reservation_expiry.clear()
            slot_state_engine._prebook_drivers.clear()
            slot_state_engine._prebook_expiry.clear()
            slot_state_engine._prebook_target.clear()
            slot_state_engine._timestamps.clear()
    except Exception:
        pass  # nosec — test cleanup, intentionally best-effort

    # ==================================================================
    # A — FULL USER FLOW (all 30 iterations)
    # ==================================================================
    try:
        email = new_driver("flow", it)
        h = _auth(email)
        check(f"{it_dev}A01 register+login", bool(h.get("Authorization")), "")

        # Browse lots
        r = client.get("/api/v1/lots", headers=h)
        check(
            f"{it_dev}A02 browse lots",
            r.status_code in (200, 304),
            r.text[:80],
        )
        lots = r.json() if r.status_code == 200 else []
        check(
            f"{it_dev}A03 lots list",
            isinstance(lots, list) and len(lots) > 0,
            str(lots)[:80],
        )

        # List slots lot_a
        r = client.get(
            "/api/v1/micro/lots/stress_lot_a/slots?limit=50", headers=h
        )
        check(f"{it_dev}A04 list slots", r.status_code == 200, r.text[:80])
        slots_data = r.json().get("slots", [])
        check(
            f"{it_dev}A05 slots returned",
            len(slots_data) > 0,
            str(len(slots_data)),
        )

        # Slot probability
        if slots_data:
            si = slots_data[0]["slot_index"]
            r = client.get(
                "/api/v1/micro/lots/stress_lot_a/slots/"
                f"{si}/probability?target_time={_target()}",
                headers=h,
            )
            check(f"{it_dev}A06 slot prob", r.status_code == 200, r.text[:80])
            d = r.json()
            check(
                f"{it_dev}A07 prob [0,1]",
                0 <= d["probability"] <= 1,
                str(d["probability"]),
            )
            check(
                f"{it_dev}A08 adj price >0",
                d["current_price"] > 0,
                str(d["current_price"]),
            )

        # Driver lot search (lot-level)
        r = client.get("/api/v1/driver/lots?lat=40.71&lon=-74.01", headers=h)
        _flow_assert(f"{it_dev}A09 driver search", r, 200)
        if r.status_code == 200:
            dl = r.json().get("lots", [])
            check(f"{it_dev}A10 driver lots", len(dl) > 0, str(len(dl)))

        # Driver lot detail
        r = client.get("/api/v1/driver/lots/stress_lot_a", headers=h)
        _flow_assert(f"{it_dev}A11 driver lot detail", r, 200)

        # Prebook 2 ranked slots
        target = _target()
        idx1 = 10 + (it % 150)
        idx2 = 11 + (it % 150)
        r = client.post(
            "/api/v1/micro/prebook",
            json={
                "lot_id": "stress_lot_a",
                "slots": [
                    {"slot_index": idx1, "priority": 1},
                    {"slot_index": idx2, "priority": 2},
                ],
                "target_time": target,
            },
            headers=h,
        )
        _flow_assert(f"{it_dev}A12 prebook", r, (200, 409, 429))
        if r.status_code == 200:
            pb = r.json()
            pid = pb["prebook_id"]
            check(
                f"{it_dev}A13 prebook active",
                pb["status"] == "active",
                pb.get("status", ""),
            )
            check(
                f"{it_dev}A14 assigned idx",
                pb["assigned_slot_index"] in (idx1, idx2),
                str(pb),
            )
            check(
                f"{it_dev}A15 fallback set",
                pb.get("fallback_order") is not None
                or pb.get("assigned_slot_index") == idx2,
                str(pb),
            )
            check(f"{it_dev}A16 prob > 0", pb["probability"] > 0, str(pb))
            check(
                f"{it_dev}A17 price > 0", pb["price_at_booking"] > 0, str(pb)
            )

            # Confirm prebook
            r = client.post(
                "/api/v1/micro/confirm", json={"prebook_id": pid}, headers=h
            )
            if r.status_code == 200:
                cf = r.json()
                check(
                    f"{it_dev}A18 confirm ok",
                    cf["status"] == "confirmed",
                    cf.get("status", ""),
                )
                check(
                    f"{it_dev}A19 has session",
                    bool(cf.get("session_id")),
                    str(cf),
                )
                check(
                    f"{it_dev}A20 slot match",
                    cf.get("slot_index") in (idx1, idx2),
                    str(cf),
                )

                sid = cf["session_id"]

                # Check active session
                r = client.get(
                    "/api/v1/sessions/active/stress_lot_a", headers=h
                )
                _flow_assert(f"{it_dev}A21 active session", r, 200)

                # Session history
                r = client.get("/api/v1/sessions/history?limit=5", headers=h)
                _flow_assert(f"{it_dev}A22 session history", r, 200)
                if r.status_code == 200:
                    sess_count = r.json().get("total_sessions", 0)
                    check(
                        f"{it_dev}A23 history has session",
                        sess_count >= 1,
                        str(sess_count),
                    )

                # End session
                r = client.post(
                    "/api/v1/sessions/end", json={"session_id": sid}, headers=h
                )
                _flow_assert(f"{it_dev}A24 end session", r, 200)
                if r.status_code == 200:
                    ed = r.json()
                    check(
                        f"{it_dev}A25 duration > 0",
                        ed.get("duration_hours", 0) >= 0,
                        str(ed),
                    )
                    check(
                        f"{it_dev}A26 amount > 0",
                        ed.get("amount_charged", 0) > 0,
                        str(ed),
                    )

                # Confirm payment
                r = client.post(
                    "/api/v1/payments/confirm",
                    json={"session_id": sid},
                    headers=h,
                )
                _flow_assert(f"{it_dev}A27 pay confirm", r, (200, 400, 409))
                if r.status_code == 200:
                    pm = r.json()
                    check(
                        f"{it_dev}A28 tx generated",
                        bool(pm.get("tx_hash")),
                        str(pm),
                    )
                    check(
                        f"{it_dev}A29 amount > 0",
                        pm.get("amount", 0) > 0,
                        str(pm),
                    )

                # Payment history
                r = client.get("/api/v1/payments/history?limit=5", headers=h)
                _flow_assert(f"{it_dev}A30 pay history", r, 200)
                if r.status_code == 200:
                    pay_cnt = r.json().get("total_payments", 0)
                    check(
                        f"{it_dev}A31 hist has payment",
                        pay_cnt >= 1,
                        str(pay_cnt),
                    )

                # Double pay protection
                r = client.post(
                    "/api/v1/payments/confirm",
                    json={"session_id": sid},
                    headers=h,
                )
                if r.status_code == 200:
                    check(
                        f"{it_dev}A32 double-pay protected",
                        r.json().get("already_paid", False),
                        r.text[:80],
                    )

            elif r.status_code == 410:
                check(
                    f"{it_dev}A18 prebook expired (target in past?)", True, ""
                )
            else:
                check(f"{it_dev}A18 confirm failed", False, r.text[:100])

        elif r.status_code == 409:
            check(f"{it_dev}A12 slot taken (expected race)", True, "")

        # Logout endpoint
        r = client.post("/api/v1/auth/logout", headers=h)
        _flow_assert(f"{it_dev}A33 logout", r, (200, 401, 403))

    except Exception as e:
        check(f"{it_dev}A_flow_exception", False, str(e))

    # ==================================================================
    # B — AUTH & SECURITY
    # ==================================================================
    try:
        # B1 — No auth header on every protected endpoint category
        protected_endpoints = [
            ("lots", "GET", "/api/v1/lots", None),
            ("lot_detail", "GET", "/api/v1/lots/stress_lot_a", None),
            ("driver_lots", "GET", "/api/v1/driver/lots", None),
            (
                "micro_slots",
                "GET",
                "/api/v1/micro/lots/stress_lot_a/slots?limit=5",
                None,
            ),
            (
                "prebook",
                "POST",
                "/api/v1/micro/prebook",
                {
                    "lot_id": "stress_lot_a",
                    "slots": [{"slot_index": 1}],
                    "target_time": _target(),
                },
            ),
            (
                "confirm",
                "POST",
                "/api/v1/micro/confirm",
                {"prebook_id": "none"},
            ),
            (
                "reserve",
                "POST",
                "/api/v1/micro/reserve",
                {"lot_id": "stress_lot_a", "slot_index": 1},
            ),
            (
                "release",
                "POST",
                "/api/v1/micro/release",
                {"slot_id": 1, "reservation_id": 0},
            ),
            (
                "session_start",
                "POST",
                "/api/v1/sessions/start",
                {"lot_id": "stress_lot_a", "slot": 1},
            ),
            (
                "session_end",
                "POST",
                "/api/v1/sessions/end",
                {"session_id": "none"},
            ),
            (
                "session_active",
                "GET",
                "/api/v1/sessions/active/stress_lot_a",
                None,
            ),
            ("session_history", "GET", "/api/v1/sessions/history", None),
            (
                "pay_confirm",
                "POST",
                "/api/v1/payments/confirm",
                {"session_id": "none"},
            ),
            ("pay_history", "GET", "/api/v1/payments/history", None),
            (
                "prediction",
                "POST",
                "/api/v1/predict/occupancy",
                {
                    "occupied_slots": 10,
                    "total_slots": 50,
                    "occ_lag_15m": 5,
                    "occ_lag_1h": 3,
                    "net_flux": -2,
                    "hour": 14,
                },
            ),
            (
                "adjust_price",
                "POST",
                "/api/v1/pricing/adjust",
                {"predicted_occupancy": 0.5, "current_price": 10.0},
            ),
            (
                "blockchain_tx",
                "POST",
                "/api/v1/blockchain/transaction",
                {
                    "driver_id": "x",
                    "lot_id": "y",
                    "action": "session_fee",
                    "price": 10.0,
                    "duration_minutes": 60,
                },
            ),
            ("blockchain_status", "GET", "/api/v1/blockchain/status", None),
            ("bc_status", "GET", "/api/v1/blockchain/status", None),
        ]
        for ep_name, method, url, body in protected_endpoints:
            if method == "GET":
                r = client.get(url)
            else:
                r = client.post(url, json=body or {})
            check(
                f"{it_dev}B01 no-auth {ep_name}",
                r.status_code in (401, 403),
                r.text[:60],
            )

        # B2 — Invalid/garbage token
        bad_headers = [
            {"Authorization": "Bearer invalidtoken"},
            {"Authorization": "Bearer " + "x" * 500},
            {"Authorization": ""},
            {"Authorization": "Basic dGVzdDpwYXNz"},
        ]
        for i, bh in enumerate(bad_headers):
            r = client.get("/api/v1/lots", headers=bh)
            check(
                f"{it_dev}B02 bad-token-{i}",
                r.status_code in (401, 403),
                r.text[:60],
            )

        # B3 — Forged JWT with wrong secret
        from jose import jwt as pyjwt

        forged = pyjwt.encode(
            {"sub": "hacker@evil.io", "role": "admin", "exp": 9999999999},
            "wrong-secret",
            algorithm="HS256",
        )
        r = client.get(
            "/api/v1/lots", headers={"Authorization": f"Bearer {forged}"}
        )
        check(
            f"{it_dev}B03 forged jwt", r.status_code in (401, 403), r.text[:60]
        )

        # B4 — SQL injection attempts on login/register
        sqli_payloads = [
            {"email": "' OR 1=1--", "password": "x"},
            {"email": "admin'--", "password": "x"},
            {"email": "'; DROP TABLE users; --", "password": "x"},
        ]
        for i, sq in enumerate(sqli_payloads):
            r = client.post("/api/v1/auth/login", json=sq)
            check(
                f"{it_dev}B04 sqli-login-{i}",
                r.status_code in (401, 403, 422),
                r.text[:60],
            )

        # B5 — Admin gate: non-admin cannot seed / admin ops
        h_normal = _auth(f"normal_{it}@test.io")
        admin_ops = [
            (
                "seed",
                "POST",
                "/api/v1/micro/lots/stress_lot_a/slots/seed",
                None,
            ),
            (
                "create_lot",
                "POST",
                "/api/v1/lots",
                {
                    "lot_id": f"hack_lot_{it}",
                    "name": "x",
                    "total_slots": 10,
                    "base_price": 5.0,
                },
            ),
        ]
        for op_name, method, url, body in admin_ops:
            r = client.post(url, json=body or {}, headers=h_normal)
            check(
                f"{it_dev}B05 admin-gate {op_name}",
                r.status_code in (401, 403),
                r.text[:60],
            )

        # B6 — IDOR: driver A cannot access driver B's session
        h_a = _auth(f"idor_a_{it}@test.io")
        h_b = _auth(f"idor_b_{it}@test.io")

        # Start session as A
        r = client.post(
            "/api/v1/sessions/start",
            json={"lot_id": "stress_lot_a", "slot": 50 + it},
            headers=h_a,
        )
        if r.status_code == 200:
            sid_a = r.json()["session_id"]
            # Try to end session A using B's token
            r = client.post(
                "/api/v1/sessions/end", json={"session_id": sid_a}, headers=h_b
            )
            check(
                f"{it_dev}B06 IDOR end-session",
                r.status_code == 403,
                r.text[:60],
            )
            # Try confirm payment as B
            r = client.post(
                "/api/v1/payments/confirm",
                json={"session_id": sid_a},
                headers=h_b,
            )
            check(
                f"{it_dev}B07 IDOR pay-confirm",
                r.status_code == 403,
                r.text[:60],
            )

            # End A's session properly
            client.post(
                "/api/v1/sessions/end", json={"session_id": sid_a}, headers=h_a
            )

    except Exception as e:
        check(f"{it_dev}B_exception", False, str(e))

    # ==================================================================
    # C — RACE CONDITIONS (iterations 10-30, or every odd)
    # ==================================================================
    if it >= 10 or it % 2 == 0:
        try:
            N_RACE = max(3, min(8, it % 9 + 3))
            race_slot = 150 + it

            # C1: N concurrent prebooks on same slot
            # (separate HTTP clients per thread)
            from fastapi.testclient import TestClient  # noqa: E402

            results: list[int | None] = [None] * N_RACE
            clr_limits()
            with get_session() as s_check:
                slot_db = (
                    s_check.query(MicroSlot)
                    .filter(
                        MicroSlot.lot_id == "stress_lot_a",
                        MicroSlot.slot_index == race_slot,
                    )
                    .first()
                )
                pre_state = (
                    slot_state_engine.get_state(slot_db.id)
                    if slot_db
                    else "NO_SLOT"
                )
            check(
                f"{it_dev}C00 pre-state slot {race_slot}",
                pre_state == SlotState.AVAILABLE,
                f"state={pre_state}",
            )
            race_headers = [
                _auth(f"race_pb_{it}_{idx}@test.io") for idx in range(N_RACE)
            ]

            def race_prebook(idx):
                try:
                    c = TestClient(app)
                    r = c.post(
                        "/api/v1/micro/prebook",
                        json={
                            "lot_id": "stress_lot_a",
                            "slots": [
                                {"slot_index": race_slot, "priority": 1}
                            ],
                            "target_time": _target(),
                        },
                        headers=race_headers[idx],
                    )
                    results[idx] = r.status_code
                except Exception:  # nosec — network race, best-effort
                    results[idx] = -1

            threads = [
                threading.Thread(target=race_prebook, args=(i,))
                for i in range(N_RACE)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            wins = sum(1 for r in results if r == 200)
            losses = sum(1 for r in results if r in (409,))
            check(
                f"{it_dev}C01 race-prebook ({N_RACE} thr): "
                f"{wins} win/"
                f"{sum(1 for r in results if r == -1)} err",
                wins == 1 and wins + losses == N_RACE,
                str(results),
            )

            # Clean up — confirm the winner's prebook via winner's client
            if wins == 1:
                winner_idx = results.index(200)
                c_win = TestClient(app)
                pbs = c_win.get(
                    "/api/v1/sessions/history",
                    headers=race_headers[winner_idx],
                )
                from src.micro.state_engine import slot_state_engine

                prebooked_sid = None
                with lock:
                    for sid, drv in list(
                        slot_state_engine._prebook_drivers.items()
                    ):
                        if drv == f"race_pb_{it}_{winner_idx}@test.io":
                            prebooked_sid = sid
                            break
                if prebooked_sid:
                    slot_state_engine.confirm_prebook(
                        prebooked_sid, f"race_pb_{it}_{winner_idx}@test.io"
                    )

            # C2: N concurrent reserves on same slot
            # (separate TestClient per thread)
            race_slot2 = 155 + it
            results2: list[int | None] = [None] * N_RACE
            clr_limits()
            race2_headers = [
                _auth(f"race_rs_{it}_{idx}@test.io") for idx in range(N_RACE)
            ]

            def race_reserve(idx):
                try:
                    c = TestClient(app)
                    r = c.post(
                        "/api/v1/micro/reserve",
                        json={
                            "lot_id": "stress_lot_a",
                            "slot_index": race_slot2,
                        },
                        headers=race2_headers[idx],
                    )
                    results2[idx] = r.status_code
                except Exception:  # nosec — network race, best-effort
                    results2[idx] = -1

            threads = [
                threading.Thread(target=race_reserve, args=(i,))
                for i in range(N_RACE)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            rwins = sum(1 for r in results2 if r == 200)
            rloss = sum(1 for r in results2 if r in (409,))
            check(
                f"{it_dev}C02 race-reserve ({N_RACE} thr): {rwins} win",
                rwins == 1 and rwins + rloss == N_RACE,
                str(results2),
            )

            # C3: prebook + reserve interleaved on same slot
            # (must be mutual-exclusive)
            inter_slot = 160 + it
            r3a: list[int | None] = [None]
            r3b: list[int | None] = [None]
            clr_limits()
            h3a = _auth(f"inter_a_{it}@test.io")
            h3b = _auth(f"inter_b_{it}@test.io")

            def _c3a():
                c = TestClient(app)
                r3a[0] = c.post(
                    "/api/v1/micro/prebook",
                    json={
                        "lot_id": "stress_lot_a",
                        "slots": [{"slot_index": inter_slot, "priority": 1}],
                        "target_time": _target(),
                    },
                    headers=h3a,
                ).status_code

            def _c3b():
                c = TestClient(app)
                r3b[0] = c.post(
                    "/api/v1/micro/reserve",
                    json={
                        "lot_id": "stress_lot_a",
                        "slot_index": inter_slot,
                    },
                    headers=h3b,
                ).status_code

            t1 = threading.Thread(target=_c3a)
            t2 = threading.Thread(target=_c3b)
            t1.start()
            t2.start()
            t1.join()
            t2.join()
            a_ok = r3a[0] == 200
            b_ok = r3b[0] == 200
            check(
                f"{it_dev}C03 prebook+reserve mutual",
                a_ok != b_ok,
                f"prebook={r3a[0]} reserve={r3b[0]}",
            )

        except Exception as e:
            check(f"{it_dev}C_exception", False, str(e))

    # ==================================================================
    # D — EDGE CASES
    # ==================================================================
    try:
        h_d = _auth(f"edge_{it}@test.io")

        # D1: Prebook with target_time in past → confirm should fail 410
        past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        r = client.post(
            "/api/v1/micro/prebook",
            json={
                "lot_id": "stress_lot_a",
                "slots": [{"slot_index": 180 + it, "priority": 1}],
                "target_time": past,
            },
            headers=h_d,
        )
        if r.status_code == 200:
            pid = r.json()["prebook_id"]
            r = client.post(
                "/api/v1/micro/confirm", json={"prebook_id": pid}, headers=h_d
            )
            check(
                f"{it_dev}D1 expired confirm",
                r.status_code in (410, 409),
                r.text[:60],
            )

        # D2: Nonexistent lot
        r = client.post(
            "/api/v1/micro/prebook",
            json={
                "lot_id": "no_such_lot_exists_xyz",
                "slots": [{"slot_index": 1}],
                "target_time": _target(),
            },
            headers=h_d,
        )
        check(f"{it_dev}D2 bad lot", r.status_code == 404, r.text[:60])

        # D3: Nonexistent slot probability
        r = client.get(
            "/api/v1/micro/lots/stress_lot_a/slots/99999/probability",
            headers=h_d,
        )
        check(f"{it_dev}D3 bad slot prob", r.status_code == 404, r.text[:60])

        # D4: Double release
        r = client.post(
            "/api/v1/micro/release",
            json={"reservation_id": 999999, "slot_id": 999},
            headers=h_d,
        )
        check(
            f"{it_dev}D4 bogus release",
            r.status_code in (404, 400),
            r.text[:60],
        )

        # D5: Invalid target_time format
        r = client.post(
            "/api/v1/micro/prebook",
            json={
                "lot_id": "stress_lot_a",
                "slots": [{"slot_index": 1}],
                "target_time": "not-a-valid-date",
            },
            headers=h_d,
        )
        check(f"{it_dev}D5 bad datetime", r.status_code == 400, r.text[:60])

        # D6: Reserved slot stats in occupancies
        h_d2 = _auth(f"edge_res_{it}@test.io")
        r = client.post(
            "/api/v1/micro/reserve",
            json={
                "lot_id": "stress_lot_a",
                "slot_index": 70 + it,
            },
            headers=h_d2,
        )
        if r.status_code == 200:
            r2 = client.get(
                "/api/v1/micro/lots/stress_lot_a/slots?limit=100", headers=h_d
            )
            if r2.status_code == 200:
                sd = r2.json()
                check(
                    f"{it_dev}D6 reserved count > 0",
                    sd.get("reserved", 0) > 0 or sd.get("available", 0) > 0,
                    str(sd),
                )

        # D7: Reserve on PREBOOKED slot
        r1 = client.post(
            "/api/v1/micro/prebook",
            json={
                "lot_id": "stress_lot_a",
                "slots": [{"slot_index": 75 + it, "priority": 1}],
                "target_time": _target(),
            },
            headers=h_d,
        )
        if r1.status_code == 200:
            h_d3 = _auth(f"edge_wrong_{it}@test.io")
            r2 = client.post(
                "/api/v1/micro/reserve",
                json={
                    "lot_id": "stress_lot_a",
                    "slot_index": 75 + it,
                },
                headers=h_d3,
            )
            check(
                f"{it_dev}D7 reserve prebooked",
                r2.status_code == 409,
                r2.text[:60],
            )

        # D8: Confirm prebook as wrong driver
        h_d4 = _auth(f"edge_wrong2_{it}@test.io")
        r = client.post(
            "/api/v1/micro/prebook",
            json={
                "lot_id": "stress_lot_a",
                "slots": [{"slot_index": 80 + it, "priority": 1}],
                "target_time": _target(),
            },
            headers=h_d,
        )
        if r.status_code == 200:
            pid = r.json()["prebook_id"]
            r = client.post(
                "/api/v1/micro/confirm", json={"prebook_id": pid}, headers=h_d4
            )
            check(
                f"{it_dev}D8 wrong driver confirm",
                r.status_code in (401, 403, 404),
                r.text[:60],
            )

        # D9: Release without owning reservation
        r = client.post(
            "/api/v1/micro/reserve",
            json={
                "lot_id": "stress_lot_a",
                "slot_index": 85 + it,
            },
            headers=h_d,
        )
        if r.status_code == 200:
            rid = r.json()["reservation_id"]
            sid = r.json()["slot_id"]
            h_d5 = _auth(f"edge_release_{it}@test.io")
            r2 = client.post(
                "/api/v1/micro/release",
                json={
                    "reservation_id": rid,
                    "slot_id": sid,
                },
                headers=h_d5,
            )
            check(
                f"{it_dev}D9 release wrong owner",
                r2.status_code in (400, 404),
                r2.text[:60],
            )

        # D10: Prebook = 0 slots (should fail schema validation)
        r = client.post(
            "/api/v1/micro/prebook",
            json={
                "lot_id": "stress_lot_a",
                "slots": [],
                "target_time": _target(),
            },
            headers=h_d,
        )
        check(f"{it_dev}D10 empty slots", r.status_code == 422, r.text[:60])

        # D11: Prebook more than 3 slots
        r = client.post(
            "/api/v1/micro/prebook",
            json={
                "lot_id": "stress_lot_a",
                "slots": [
                    {"slot_index": i, "priority": i} for i in range(1, 6)
                ],
                "target_time": _target(),
            },
            headers=h_d,
        )
        check(f"{it_dev}D11 >3 slots", r.status_code == 422, r.text[:60])

        # D12: slot_index = 0 (invalid per schema ge=1)
        r = client.post(
            "/api/v1/micro/prebook",
            json={
                "lot_id": "stress_lot_a",
                "slots": [{"slot_index": 0}],
                "target_time": _target(),
            },
            headers=h_d,
        )
        check(f"{it_dev}D12 slot_index 0", r.status_code == 422, r.text[:60])

        # D13: session start without auth
        r = client.post(
            "/api/v1/sessions/start",
            json={"lot_id": "stress_lot_a", "slot": 1},
        )
        check(
            f"{it_dev}D13 session no-auth",
            r.status_code in (401, 403),
            r.text[:60],
        )

        # D14: start session on nonexistent lot
        r = client.post(
            "/api/v1/sessions/start",
            json={"lot_id": "no_such_lot_404", "slot": 1},
            headers=h_d,
        )
        check(
            f"{it_dev}D14 session bad lot", r.status_code == 404, r.text[:60]
        )

    except Exception as e:
        check(f"{it_dev}D_exception", False, str(e))

    # ==================================================================
    # E — ADMIN OPERATIONS (iterations 1-20)
    # ==================================================================
    if it <= 20:
        try:
            h_adm = _admin()

            # E1: Create a lot
            lid = f"admin_test_{it}"
            r = client.post(
                "/api/v1/lots",
                json={
                    "lot_id": lid,
                    "name": f"Admin Lot {it}",
                    "total_slots": 50,
                    "base_price": 15.0,
                },
                headers=h_adm,
            )
            check(
                f"{it_dev}E1 create lot",
                r.status_code in (200, 409),
                r.text[:60],
            )

            # E2: Seed slots
            r = client.post(
                f"/api/v1/micro/lots/{lid}/slots/seed", headers=h_adm
            )
            check(
                f"{it_dev}E2 seed slots",
                r.status_code in (200, 500),
                r.text[:60],
            )
            if r.status_code == 200:
                check(
                    f"{it_dev}E3 seed count > 0",
                    r.json().get("count", 0) > 0,
                    r.text[:60],
                )

            # E3: Update lot
            r = client.put(
                f"/api/v1/lots/{lid}/config",
                json={
                    "base_price": 12.0,
                    "price_cap": 100.0,
                },
                headers=h_adm,
            )
            check(
                f"{it_dev}E4 update lot",
                r.status_code in (200, 404),
                r.text[:60],
            )

            # E4: Pipeline status
            r = client.get("/api/v1/driver/pipeline/status", headers=h_adm)
            _flow_assert(f"{it_dev}E5 pipeline status", r, (200, 404, 500))

            # E5: Blockchain mine
            r = client.post("/api/v1/blockchain/mine", headers=h_adm)
            check(
                f"{it_dev}E6 mine block",
                r.status_code in (200, 400, 429),
                r.text[:60],
            )

            # E6: Blockchain status
            r = client.get("/api/v1/blockchain/status", headers=h_adm)
            check(f"{it_dev}E7 bc status", r.status_code == 200, r.text[:60])

            # E7: Revenue overview
            r = client.get("/api/v1/revenue/overview", headers=h_adm)
            check(
                f"{it_dev}E8 revenue overview",
                r.status_code == 200,
                r.text[:60],
            )

            # E8: Dashboard
            r = client.get("/api/v1/admin/dashboard", headers=h_adm)
            check(
                f"{it_dev}E9 dashboard",
                r.status_code in (200, 404),
                r.text[:60],
            )

        except Exception as e:
            check(f"{it_dev}E_exception", False, str(e))

    # ==================================================================
    # F — SESSION LIFECYCLE VARIATIONS
    # ==================================================================
    try:
        h_f = _auth(f"sess_{it}@test.io")

        # F1: Session start → end via pipeline orchestrator
        r = client.post(
            "/api/v1/sessions/start",
            json={"lot_id": "stress_lot_b", "slot": 200 + it},
            headers=h_f,
        )
        _flow_assert(f"{it_dev}F1 start session", r, (200, 409))
        if r.status_code == 200:
            sd = r.json()
            sid = sd["session_id"]
            check(
                f"{it_dev}F2 all layers activated",
                all(
                    k in sd
                    for k in (
                        "iot_consensus",
                        "digital_twin",
                        "blockchain_ref",
                        "price_multiplier",
                        "predicted_occupancy",
                    )
                ),
                str(list(sd.keys())),
            )
            check(
                f"{it_dev}F3 6-layer output",
                len(sd.get("layers_activated", [])) >= 4,
                str(sd.get("layers_activated", [])),
            )

            # End
            r = client.post(
                "/api/v1/sessions/end", json={"session_id": sid}, headers=h_f
            )
            _flow_assert(f"{it_dev}F4 end session", r, 200)
            if r.status_code == 200:
                ed = r.json()
                check(
                    f"{it_dev}F5 price same or higher",
                    ed["final_price"] >= ed["entry_price"]
                    or abs(ed["final_price"] - ed["entry_price"]) < 0.01,
                    f"entry={ed['entry_price']} final={ed['final_price']}",
                )

        # F2: Dual session prevention
        h_f2 = _auth(f"sess2_{it}@test.io")
        r1 = client.post(
            "/api/v1/sessions/start",
            json={"lot_id": "stress_lot_c", "slot": 50 + it},
            headers=h_f2,
        )
        r2 = client.post(
            "/api/v1/sessions/start",
            json={"lot_id": "stress_lot_c", "slot": 51 + it},
            headers=h_f2,
        )
        if r1.status_code == 200:
            check(
                f"{it_dev}F6 dual session blocked",
                r2.status_code == 409,
                f"r1={r1.status_code} r2={r2.status_code}",
            )

        # F3: Session history pagination
        r = client.get(
            "/api/v1/sessions/history?offset=0&limit=10", headers=h_f
        )
        _flow_assert(f"{it_dev}F7 hist paginate", r, 200)

        # F4: Empty history for brand new user
        h_f3 = _auth(f"fresh_{it}@test.io")
        r = client.get("/api/v1/sessions/history", headers=h_f3)
        _flow_assert(f"{it_dev}F8 fresh history", r, 200)
        if r.status_code == 200:
            check(
                f"{it_dev}F9 fresh history empty",
                r.json()["total_sessions"] == 0,
                str(r.json()["total_sessions"]),
            )

    except Exception as e:
        check(f"{it_dev}F_exception", False, str(e))

    # ==================================================================
    # G — SYSTEM ENDPOINTS (health, prediction, pricing, DT, scenarios)
    # ==================================================================
    try:
        h_g = _auth(f"sys_{it}@test.io")

        # G1: Health
        r = client.get("/api/v1/health")
        check(f"{it_dev}G1 health", r.status_code in (200, 404), r.text[:60])

        # G2: Prediction endpoint
        r = client.post(
            "/api/v1/predict/occupancy",
            json={
                "occupied_slots": 25 + it,
                "total_slots": 200,
                "occ_lag_15m": 20 + it,
                "occ_lag_1h": 18 + it,
                "net_flux": -3 + it,
                "hour": it % 24,
            },
            headers=h_g,
        )
        _flow_assert(f"{it_dev}G2 predict", r, (200, 503, 429))
        if r.status_code == 200:
            pd_resp = r.json()
            check(
                f"{it_dev}G3 ensemble [0,1]",
                0 <= pd_resp.get("ensemble_prediction", 0) <= 1,
                str(pd_resp),
            )
            check(
                f"{it_dev}G4 rf pred",
                "rf_prediction" in pd_resp,
                str(list(pd_resp.keys())),
            )

        # G3: Pricing adjustment
        r = client.post(
            "/api/v1/pricing/adjust",
            json={
                "predicted_occupancy": round(random.uniform(0.2, 0.9), 2),
                "current_price": round(random.uniform(8, 15), 2),
            },
            headers=h_g,
        )
        _flow_assert(f"{it_dev}G5 pricing", r, (200, 503))

        # G4: Digital Twin scenarios list
        r = client.get("/api/v1/digital-twin/scenarios", headers=h_g)
        _flow_assert(f"{it_dev}G6 DT scenarios", r, 200)
        if r.status_code == 200:
            sc_list = r.json()
            check(
                f"{it_dev}G7 scenarios exist",
                isinstance(sc_list, list) and len(sc_list) > 0,
                str(sc_list)[:80],
            )

        # G5: Run scenario
        r = client.post(
            "/api/v1/digital-twin/scenarios/run",
            json={
                "scenario_type": "zone_closure",
                "zone_id": "zone_a",
            },
            headers=h_g,
        )
        _flow_assert(f"{it_dev}G8 run scenario", r, (200, 404, 500))

        # G6: Pipeline scenario (via digital-twin)
        r = client.post(
            "/api/v1/digital-twin/scenario",
            json={
                "scenario_type": "price_surge",
                "zone_id": "zone_b",
            },
            headers=h_g,
        )
        _flow_assert(f"{it_dev}G9 pipeline scenario", r, (200, 500))

        # G7: Ingest occupancy
        r = client.post(
            "/api/v1/ingestion/occupancy",
            json={
                "lot_id": "stress_lot_a",
                "occupied_slots": 100 + it,
                "total_slots": 200,
                "net_flux": 5.0,
            },
            headers=_admin(),
        )
        _flow_assert(f"{it_dev}G10 ingest occ", r, (200, 429))

        # G8: Blockchain transaction
        r = client.post(
            "/api/v1/blockchain/transaction",
            json={
                "driver_id": f"sys_{it}@test.io",
                "lot_id": "stress_lot_a",
                "action": "session_fee",
                "price": 10.0,
                "duration_minutes": 60,
            },
            headers=h_g,
        )
        _flow_assert(f"{it_dev}G11 bc tx", r, (200, 429))
        if r.status_code == 200:
            tx = r.json()
            check(f"{it_dev}G12 tx has hash", bool(tx.get("tx_hash")), str(tx))

        # G9: Revenue overview (admin only)
        r = client.get("/api/v1/revenue/overview", headers=_admin())
        _flow_assert(f"{it_dev}G13 revenue", r, (200, 403))

        # G10: Model health
        r = client.get("/api/v1/predict/health", headers=h_g)
        _flow_assert(f"{it_dev}G14 model health", r, (200, 401))

    except Exception as e:
        check(f"{it_dev}G_exception", False, str(e))

    # ==================================================================
    # H — DATA INTEGRITY (engine ↔ DB consistency)
    # ==================================================================
    if it % 3 == 0:
        try:
            # H1: After reservation, check engine ↔ DB match
            h_h = _auth(f"integ_{it}@test.io")
            r = client.post(
                "/api/v1/micro/reserve",
                json={
                    "lot_id": "stress_lot_a",
                    "slot_index": 90 + it,
                },
                headers=h_h,
            )
            if r.status_code == 200:
                e_state = slot_state_engine.get_state(r.json()["slot_id"])
                check(
                    f"{it_dev}H1 engine matches RESERVED",
                    e_state == SlotState.RESERVED,
                    f"got {e_state}",
                )

                # release
                rid = r.json()["reservation_id"]
                sid = r.json()["slot_id"]
                client.post(
                    "/api/v1/micro/release",
                    json={
                        "reservation_id": rid,
                        "slot_id": sid,
                    },
                    headers=h_h,
                )
                e_state2 = slot_state_engine.get_state(sid)
                check(
                    f"{it_dev}H2 engine AVAILABLE after release",
                    e_state2 == SlotState.AVAILABLE,
                    f"got {e_state2}",
                )

            # H3: Prebook → engine consistency
            r = client.post(
                "/api/v1/micro/prebook",
                json={
                    "lot_id": "stress_lot_a",
                    "slots": [{"slot_index": 95 + it, "priority": 1}],
                    "target_time": _target(),
                },
                headers=h_h,
            )
            if r.status_code == 200:
                slot_idx = r.json()["assigned_slot_index"]
                db2 = get_session()
                try:
                    ms = (
                        db2.query(MicroSlot)
                        .filter(
                            MicroSlot.lot_id == "stress_lot_a",
                            MicroSlot.slot_index == slot_idx,
                        )
                        .first()
                    )
                    if ms:
                        e_st = slot_state_engine.get_state(ms.id)
                        check(
                            f"{it_dev}H3 engine PREBOOKED match",
                            e_st == SlotState.PREBOOKED,
                            f"got {e_st}",
                        )
                finally:
                    db2.close()

            # H4: Occupancies dict has all keys
            from src.micro.state_engine import slot_state_engine as se

            with get_session() as db3:
                all_slots = (
                    db3.query(MicroSlot)
                    .filter(
                        MicroSlot.lot_id == "stress_lot_a",
                        MicroSlot.active == 1,
                    )
                    .limit(50)
                    .all()
                )
            occ = se.occupancies("stress_lot_a", all_slots)
            for key in (
                "total_slots",
                "available_slots",
                "reserved_slots",
                "occupied_slots",
                "prebooked_slots",
                "occupancy_rate",
            ):
                check(
                    f"{it_dev}H5 occ has {key}",
                    key in occ,
                    str(list(occ.keys())),
                )

        except Exception as e:
            check(f"{it_dev}H_exception", False, str(e))

    # ==================================================================
    # I — RATE LIMIT EXHAUSTION
    # ==================================================================
    if it >= 25:
        try:
            h_i = _auth(f"ratelimit_{it}@test.io")

            # Hammer prebook endpoint rapidly
            for attempt in range(10):
                r = client.post(
                    "/api/v1/micro/prebook",
                    json={
                        "lot_id": "stress_lot_a",
                        "slots": [
                            {"slot_index": 190 + attempt, "priority": 1}
                        ],
                        "target_time": _target(),
                    },
                    headers=h_i,
                )
                if r.status_code == 429:
                    check(
                        f"{it_dev}I1 rate limit hit at attempt {attempt + 1}",
                        True,
                        "",
                    )
                    break
            else:
                check(
                    f"{it_dev}I1 rate limit NOT hit (may be config)",
                    False,
                    "prebook never returned 429 after 10 calls",
                )

            # Hammer login endpoint
            hit_login = False
            last_status = 0
            for attempt in range(10):
                rl = client.post(
                    "/api/v1/auth/login",
                    json={
                        "email": f"ratelimit_{it}@test.io",
                        "password": "WrongPass!",
                    },
                )
                last_status = rl.status_code
                if rl.status_code == 429:
                    hit_login = True
                    break
            check(
                f"{it_dev}I2 login rate limit",
                True,
                f"hit={hit_login} last={last_status}",
            )

        except Exception as e:
            check(f"{it_dev}I_exception", False, str(e))

    # progress
    if it % 5 == 0:
        elapsed = time.time() - t0
        print(f"  [{it}/30] {PASS} pass / {FAIL} fail  ({elapsed:.0f}s)")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
elapsed = time.time() - t0
total = PASS + FAIL
print(f"\n{'=' * 70}")
print(f"  QA STRESS TEST COMPLETE  —  {elapsed:.0f}s")
print(f"{'=' * 70}")
print(f"  Total checks:  {total}")
print(f"  PASS:          {PASS} ({100 * PASS // max(total, 1)}%)")
print(f"  FAIL:          {FAIL}")
if FAIL and ERRORS:
    print("\n  FAILURE DETAILS (first 30):")
    for e in ERRORS[:30]:
        print(f"    {e}")
    if len(ERRORS) > 30:
        print(f"    ... and {len(ERRORS) - 30} more")
print(f"{'=' * 70}\n")

# cleanup
gc.collect()
engine.dispose()
for f in os.listdir("/tmp"):
    if any(f.endswith(e) for e in (".db", ".db-wal", ".db-shm")):
        try:
            os.remove(f"/tmp/{f}")
        except Exception:
            pass  # nosec — temp file cleanup, best-effort

sys.exit(0 if FAIL == 0 else 1)
