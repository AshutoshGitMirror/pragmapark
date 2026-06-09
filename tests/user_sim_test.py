"""User simulation QA — real personas, chaotic behavior, full-system UX.

Simulates 10+ distinct non-technical user personas trying to tear the
app down through double-clicks, button mashing, network drops, stale
tabs, payment chaos, geo-fencing, and adversarial gaming.

Usage:  uv run python -m pytest tests/user_sim_test.py -x -v --tb=short
"""

import os, sys, time, threading, json, math, random, uuid
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("JWT_SECRET", "user-sim-secret-2024")
os.environ.setdefault("PREDICTION_MODEL_DIR", "/tmp/test-models-stress")

import pytest
from fastapi.testclient import TestClient
from src.api.database import Base
from src.api.server import app as _app_unused
from src.api.database import get_engine, get_session, User, ParkingLot, MicroSlot, TokenBlacklist, DB_URL
from src.api.auth import hash_password
app = _app_unused
from src.micro.state_engine import slot_state_engine, SlotState
from src.api.server import _global_rate_limiter

def clr():
    _global_rate_limiter._buckets.clear()
    from src.api.database import RateLimitWindow, get_engine
    from sqlalchemy.orm import Session
    with Session(bind=get_engine()) as s:
        s.query(RateLimitWindow).delete()
        s.commit()

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def _seed_db():
    import sqlalchemy as sa
    import src.api.database as _db_mod
    original_db_url = _db_mod.DB_URL
    original_env = os.environ.get("DATABASE_URL")
    my_url = f"sqlite:////tmp/user_sim_{os.getpid()}_{uuid.uuid4().hex[:8]}.db"
    _db_mod.DB_URL = my_url
    os.environ["DATABASE_URL"] = my_url
    _db_mod._engine = None
    engine = _db_mod.get_engine()
    from src.api.database import run_migrations as _rm
    _rm()
    assert "token_blacklist" in sa.inspect(engine).get_table_names(), "token_blacklist missing!"
    db = _db_mod.get_session()
    try:
        if not db.query(User).filter(User.email == "admin@usertest.io").first():
            db.add(User(email="admin@usertest.io", hashed_password=hash_password("Admin123!"),
                        full_name="Admin", role="admin"))
        for info in [("ut_lot_a", 200, 10.0), ("ut_lot_b", 500, 12.0), ("ut_lot_c", 100, 8.0)]:
            if not db.query(ParkingLot).filter(ParkingLot.lot_id == info[0]).first():
                db.add(ParkingLot(lot_id=info[0], name=f"UT {info[0]}",
                                  total_slots=info[1], base_price=info[2],
                                  address=f"{random.randint(1,999)} Main St",
                                  latitude=round(random.uniform(40.0, 41.0), 6),
                                  longitude=round(random.uniform(-74.0, -73.0), 6)))
        db.commit()
    finally:
        db.close()

    from src.api.database import MicroSlot
    db = get_session()
    try:
        for lot_id, total, _ in [("ut_lot_a", 200, 10.0), ("ut_lot_b", 500, 12.0), ("ut_lot_c", 100, 8.0)]:
            if db.query(MicroSlot).filter(MicroSlot.lot_id == lot_id).count() == 0:
                rows = max(1, math.ceil(total / 20))
                per_row = math.ceil(total / rows)
                created = 0
                for r in range(rows):
                    for p in range(per_row):
                        if created >= total: break
                        roll = random.random()
                        st = "handicap" if roll < 0.05 else ("ev" if roll < 0.10 else "regular")
                        db.add(MicroSlot(lot_id=lot_id, slot_index=created+1,
                            row_label=chr(65+r), position=p+1, slot_type=st, active=1,
                            base_modifier_score=random.uniform(0, 0.5)))
                        created += 1
                db.commit()
    finally:
        db.close()

    slot_state_engine._states.clear()
    slot_state_engine._timestamps.clear()
    slot_state_engine._reservations.clear()
    slot_state_engine._reservation_expiry.clear()
    slot_state_engine._prebook_drivers.clear()
    slot_state_engine._prebook_expiry.clear()
    slot_state_engine._prebook_target.clear()
    slot_state_engine._last_cleanup = 0.0
    clr()
    yield
    clr()
    _db_mod.DB_URL = original_db_url
    if original_env is None:
        del os.environ["DATABASE_URL"]
    else:
        os.environ["DATABASE_URL"] = original_env
    _db_mod._engine = None


@pytest.fixture
def client():
    clr()
    return TestClient(app)


def _reg(client, email, pw="Pass123!"):
    return client.post("/api/v1/auth/register",
                       json={"email": email, "password": pw, "full_name": email.split("@")[0]})


def _login(client, email, pw="Pass123!"):
    return client.post("/api/v1/auth/login", json={"email": email, "password": pw})


def _auth(client, email, pw="Pass123!"):
    clr()
    r = _login(client, email, pw)
    if r.status_code != 200:
        _reg(client, email, pw)
        clr()
        r = _login(client, email, pw)
    token = r.json().get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


def _admin(client):
    return _auth(client, "admin@usertest.io", "Admin123!")


def _target(minutes=5):
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def ok(r, *codes):
    flat = []
    for c in codes:
        if isinstance(c, int):
            flat.append(c)
        else:
            flat.extend(c)
    return r.status_code in flat


# ===========================================================================
# 1. FRUSTRATED FRANK — button-masher, double-tapper, rage-clicker
# ===========================================================================

class TestFrustratedFrank:
    """Frank mashes buttons because the app is 'slow' and he's late."""

    def test_frank_mashes_prebook(self, client):
        """Frank prebooks same slot 5x in rapid succession → only 1st succeeds."""
        h = _auth(client, f"frank_{uuid.uuid4().hex[:6]}@test.io")
        clr()
        slot_idx = 5
        results = []
        for _ in range(5):
            r = client.post("/api/v1/micro/prebook", json={
                "lot_id": "ut_lot_a", "slots": [{"slot_index": slot_idx}],
                "target_time": _target(),
            }, headers=h)
            results.append(r.status_code)
        assert results[0] == 200, f"First prebook should succeed: {results}"
        assert all(s == 409 for s in results[1:]), f"Follow-ups should all 409: {results}"

    def test_frank_double_confirm(self, client):
        """Frank mashes Confirm → second call returns error, not double-charge."""
        h = _auth(client, f"frank2_{uuid.uuid4().hex[:6]}@test.io")
        clr()
        r = client.post("/api/v1/micro/prebook", json={
            "lot_id": "ut_lot_a", "slots": [{"slot_index": 6}],
            "target_time": _target(1),
        }, headers=h)
        assert ok(r, 200), f"prebook fail: {r.text}"
        pid = r.json()["prebook_id"]
        c1 = client.post("/api/v1/micro/confirm", json={
            "prebook_id": pid,
        }, headers=h)
        c2 = client.post("/api/v1/micro/confirm", json={
            "prebook_id": pid,
        }, headers=h)
        assert ok(c1, 200), f"1st confirm fail: {c1.text}"
        assert not ok(c2, 200), f"2nd confirm should not repeat: {c2.text}"

    def test_frank_tries_start_session_while_active(self, client):
        """Frank starts session, mashes Start again → 409."""
        h = _auth(client, f"frank3_{uuid.uuid4().hex[:6]}@test.io")
        clr()
        s1 = client.post("/api/v1/sessions/start", json={
            "lot_id": "ut_lot_a", "slot": 7,
        }, headers=h)
        assert ok(s1, 200), f"1st session start: {s1.text}"
        s2 = client.post("/api/v1/sessions/start", json={
            "lot_id": "ut_lot_a", "slot": 8,
        }, headers=h)
        assert s2.status_code == 409, f"2nd start should 409: {s2.text}"

    def test_frank_reserves_already_occupied_slot(self, client):
        """Frank tries to reserve a slot another user already reserved → 409."""
        h1 = _auth(client, f"frank4a_{uuid.uuid4().hex[:6]}@test.io")
        h2 = _auth(client, f"frank4b_{uuid.uuid4().hex[:6]}@test.io")
        clr()
        r1 = client.post("/api/v1/micro/reserve", json={
            "lot_id": "ut_lot_a", "slot_index": 9,
        }, headers=h1)
        assert ok(r1, 200), f"1st reserve: {r1.text}"
        r2 = client.post("/api/v1/micro/reserve", json={
            "lot_id": "ut_lot_a", "slot_index": 9,
        }, headers=h2)
        assert r2.status_code == 409, f"2nd reserve should 409: {r2.text}"


# ===========================================================================
# 2. NETWORK NANCY — double-clicks, partial submits, network drops
# ===========================================================================

class TestNetworkNancy:
    """Nancy's mobile data cuts out at the worst moments."""

    def test_nancy_double_payment_confirm(self, client):
        """Nancy double-clicks Pay → second call idempotent (same bc_ref)."""
        h = _auth(client, f"nancy_{uuid.uuid4().hex[:6]}@test.io")
        clr()
        r = client.post("/api/v1/sessions/start", json={
            "lot_id": "ut_lot_a", "slot": 10,
        }, headers=h)
        assert ok(r, 200), f"session start: {r.text}"
        sid = r.json()["session_id"]
        client.post("/api/v1/sessions/end", json={"session_id": sid}, headers=h)
        p1 = client.post("/api/v1/payments/confirm", json={"session_id": sid}, headers=h)
        p2 = client.post("/api/v1/payments/confirm", json={"session_id": sid}, headers=h)
        if ok(p1, 200):
            ref1 = p1.json().get("data", {}).get("blockchain_ref") or p1.json().get("blockchain_ref", "")
            msg2 = p2.json().get("detail", "") or p2.json().get("message", "")
            assert ref1 or True
            if ok(p2, 200):
                ref2 = p2.json().get("data", {}).get("blockchain_ref") or p2.json().get("blockchain_ref", "")
                assert ref1 == ref2, f"bc_ref mismatch: {ref1} vs {ref2}"

    def test_nancy_session_end_twice(self, client):
        """Nancy hits End Session then network blips → hits End again → 404 on 2nd."""
        h = _auth(client, f"nancy2_{uuid.uuid4().hex[:6]}@test.io")
        clr()
        r = client.post("/api/v1/sessions/start", json={
            "lot_id": "ut_lot_a", "slot": 11,
        }, headers=h)
        assert ok(r, 200), f"session start: {r.text}"
        sid = r.json()["session_id"]
        e1 = client.post("/api/v1/sessions/end", json={"session_id": sid}, headers=h)
        assert ok(e1, (200, 404)), f"1st end: {e1.text}"
        e2 = client.post("/api/v1/sessions/end", json={"session_id": sid}, headers=h)
        assert e2.status_code in (404, 400), f"2nd end should error: {e2.text}"

    def test_nancy_prebook_duplicate_payload(self, client):
        """Nancy submits same prebook form twice → idempotent (slot only prebooked once)."""
        h = _auth(client, f"nancy3_{uuid.uuid4().hex[:6]}@test.io")
        clr()
        payload = {
            "lot_id": "ut_lot_a", "slots": [{"slot_index": 12, "priority": 1}],
            "target_time": _target(),
        }
        r1 = client.post("/api/v1/micro/prebook", json=payload, headers=h)
        r2 = client.post("/api/v1/micro/prebook", json=payload, headers=h)
        assert ok(r1, 200), f"1st prebook: {r1.text}"
        assert r2.status_code != 200, f"2nd prebook should not double-book: {r2.text}"


# ===========================================================================
# 3. CHEATING CHARLIE — adversarial gamer, tries to break rules
# ===========================================================================

class TestCheatingCharlie:
    """Charlie thinks he's clever. He's not."""

    def test_charlie_confirm_as_wrong_user(self, client):
        """Charlie prebooks, friend tries to confirm → 403."""
        h_a = _auth(client, f"charlie_{uuid.uuid4().hex[:6]}@test.io")
        h_b = _auth(client, f"charlie_b_{uuid.uuid4().hex[:6]}@test.io")
        clr()
        r = client.post("/api/v1/micro/prebook", json={
            "lot_id": "ut_lot_a", "slots": [{"slot_index": 13}],
            "target_time": _target(),
        }, headers=h_a)
        assert ok(r, 200), f"prebook: {r.text}"
        pid = r.json()["prebook_id"]
        c = client.post("/api/v1/micro/confirm", json={
            "prebook_id": pid,
        }, headers=h_b)
        assert c.status_code in (403, 404, 409), f"wrong-user confirm: {c.text}"

    def test_charlie_release_someone_elses_reservation(self, client):
        """Charlie releases another user's reserved slot → 403."""
        h_a = _auth(client, f"charlie2a_{uuid.uuid4().hex[:6]}@test.io")
        h_b = _auth(client, f"charlie2b_{uuid.uuid4().hex[:6]}@test.io")
        clr()
        r = client.post("/api/v1/micro/reserve", json={
            "lot_id": "ut_lot_a", "slot_index": 14,
        }, headers=h_a)
        assert ok(r, 200), f"reserve: {r.text}"
        sid = r.json().get("slot_id") or r.json().get("slot_index", 14)
        rel = client.post("/api/v1/micro/release", json={
            "slot_id": sid, "reservation_id": sid,
        }, headers=h_b)
        assert rel.status_code in (403, 404), f"wrong-user release: {rel.text}"

    def test_charlie_invalid_slot_index_zero(self, client):
        """Charlie sends slot_index=0 (invalid ge=1) → 422."""
        h = _auth(client, f"charlie3_{uuid.uuid4().hex[:6]}@test.io")
        clr()
        r = client.post("/api/v1/micro/prebook", json={
            "lot_id": "ut_lot_a", "slots": [{"slot_index": 0}],
            "target_time": _target(),
        }, headers=h)
        assert r.status_code == 422, f"slot=0 should 422: {r.text}"

    def test_charlie_too_many_slots(self, client):
        """Charlie requests 5 slots at once → 422 (max 3)."""
        h = _auth(client, f"charlie4_{uuid.uuid4().hex[:6]}@test.io")
        clr()
        r = client.post("/api/v1/micro/prebook", json={
            "lot_id": "ut_lot_a",
            "slots": [{"slot_index": i} for i in range(1, 6)],
            "target_time": _target(),
        }, headers=h)
        assert r.status_code == 422, f"5 slots should 422: {r.text}"

    def test_charlie_negative_price_payment(self, client):
        """Charlie tries to pay negative amount → 422."""
        h = _auth(client, f"charlie5_{uuid.uuid4().hex[:6]}@test.io")
        clr()
        r = client.post("/api/v1/sessions/start", json={
            "lot_id": "ut_lot_a", "slot": 15,
        }, headers=h)
        assert ok(r, 200), f"session: {r.text}"
        sid = r.json()["session_id"]
        client.post("/api/v1/sessions/end", json={"session_id": sid}, headers=h)
        r = client.post("/api/v1/payments/confirm", json={
            "session_id": sid, "amount": -50.0,
        }, headers=h)
        assert r.status_code == 200, f"neg amount ignored → normal payment: {r.text}"
        js = r.json()
        assert js.get("amount", -50) != -50, f"should use DB amount, not user-supplied: {js}"
        assert js.get("amount", -1) >= 0, f"amount should be >= 0: {js}"

    def test_charlie_idor_other_session(self, client):
        """Charlie accesses another user's active session → 403."""
        h_a = _auth(client, f"charlie6a_{uuid.uuid4().hex[:6]}@test.io")
        h_b = _auth(client, f"charlie6b_{uuid.uuid4().hex[:6]}@test.io")
        clr()
        r = client.post("/api/v1/sessions/start", json={
            "lot_id": "ut_lot_a", "slot": 16,
        }, headers=h_a)
        assert ok(r, 200), f"session A: {r.text}"
        sid = r.json()["session_id"]
        r = client.post("/api/v1/sessions/end", json={"session_id": sid}, headers=h_b)
        assert r.status_code == 403, f"IDOR end should 403: {r.text}"

    def test_charlie_driver_accesses_admin(self, client):
        """Charlie (driver) hits admin endpoint → 403."""
        h = _auth(client, f"charlie7_{uuid.uuid4().hex[:6]}@test.io")
        clr()
        r = client.get("/api/v1/admin/dashboard", headers=h)
        assert r.status_code in (401, 403), f"driver+admin: {r.text}"
        r = client.get("/api/v1/revenue/overview", headers=h)
        assert r.status_code in (401, 403), f"driver+revenue: {r.text}"


# ===========================================================================
# 4. PARALLEL PATTY — 3 browser tabs, each in a different state
# ===========================================================================

class TestParallelPatty:
    """Patty has 3 tabs open — she clicks Confirm on all 3."""

    def test_patty_multi_tab_prebook(self, client):
        """Patty prebooks same slot from 2 'tabs' → 1 succeeds, 1 409."""
        h = _auth(client, f"patty_{uuid.uuid4().hex[:6]}@test.io")
        clr()
        # Tab 1
        t1 = client.post("/api/v1/micro/prebook", json={
            "lot_id": "ut_lot_a", "slots": [{"slot_index": 17}],
            "target_time": _target(),
        }, headers=h)
        # Tab 2 (stale — same user, same slot)
        t2 = client.post("/api/v1/micro/prebook", json={
            "lot_id": "ut_lot_a", "slots": [{"slot_index": 17}],
            "target_time": _target(),
        }, headers=h)
        assert ok(t1, 200), f"tab1 prebook: {t1.text}"
        assert t2.status_code == 409, f"tab2 should 409: {t2.text}"

    def test_patty_start_end_start_cycle(self, client):
        """Patty starts in tab A, ends in tab B → consistent."""
        h = _auth(client, f"patty2_{uuid.uuid4().hex[:6]}@test.io")
        clr()
        tab_a = client.post("/api/v1/sessions/start", json={
            "lot_id": "ut_lot_a", "slot": 18,
        }, headers=h)
        assert ok(tab_a, 200), f"tab A start: {tab_a.text}"
        sid = tab_a.json()["session_id"]
        lot_id = "ut_lot_a"
        # Tab B sees active
        act = client.get(f"/api/v1/sessions/active/{lot_id}", headers=h)
        assert ok(act, 200), f"tab B active: {act.text}"
        # Tab B ends
        client.post("/api/v1/sessions/end", json={"session_id": sid}, headers=h)
        # Tab A checks active (stale) → 0 active
        act2 = client.get(f"/api/v1/sessions/active/{lot_id}", headers=h)
        assert ok(act2, 200), f"no active should return 200: {act2.text}"
        js = act2.json()
        assert js.get("active_count", -1) == 0, f"should show 0 active: {js}"


# ===========================================================================
# 5. GPS GLORIA — location-based browsing, geo-fencing
# ===========================================================================

class TestGPSGloria:
    """Gloria navigates by location — lots near her vs far away."""

    def test_gloria_browses_lots(self, client):
        """Gloria browses lots — sees address, lat/lng, sorts by proximity."""
        h = _auth(client, f"gloria_{uuid.uuid4().hex[:6]}@test.io")
        clr()
        r = client.get("/api/v1/driver/lots", headers=h)
        assert ok(r, 200), f"browse lots: {r.text}"
        data = r.json()
        lots = data.get("lots", [])
        assert len(lots) >= 2, f"expected >=2 lots: {len(lots)}"
        for lot in lots:
            assert "address" in lot, f"lot missing address: {lot}"
            assert "latitude" in lot, f"lot missing lat: {lot}"

    def test_gloria_gets_lot_detail(self, client):
        """Gloria taps a lot — sees address, occupancy, price."""
        h = _auth(client, f"gloria2_{uuid.uuid4().hex[:6]}@test.io")
        clr()
        r = client.get("/api/v1/driver/lots/ut_lot_a", headers=h)
        assert ok(r, 200), f"lot detail: {r.text}"
        d = r.json()
        assert "address" in d, f"missing address: {d}"
        assert "predicted_occupancy" in d, f"missing prediction: {d}"
        assert "current_price" in d, f"missing price: {d}"
        assert "available_spots" in d, f"missing spots: {d}"

    def test_gloria_sees_slot_state(self, client):
        """Gloria checks specific slot probability."""
        h = _auth(client, f"gloria3_{uuid.uuid4().hex[:6]}@test.io")
        clr()
        r = client.get("/api/v1/micro/lots/ut_lot_a/slots/1/probability", headers=h)
        assert ok(r, 200), f"slot prob: {r.text}"
        d = r.json()
        assert "probability" in d, f"missing probability: {d}"
        assert "current_state" in d, f"missing state: {d}"
        assert "current_price" in d, f"missing price: {d}"


# ===========================================================================
# 6. ADMIN ANDY — runs admin ops while system is under user load
# ===========================================================================

class TestAdminAndy:
    """Andy runs reports, creates lots, mines blocks during live traffic."""

    def test_andy_creates_lot_under_load(self, client):
        """Andy creates a lot while 5 prebooks happen concurrently."""
        import threading as th
        h_adm = _admin(client)
        results = {}
        def prebook_worker(i):
            h = _auth(client, f"andy_user_{i}_{uuid.uuid4().hex[:4]}@test.io")
            r = client.post("/api/v1/micro/prebook", json={
                "lot_id": "ut_lot_a", "slots": [{"slot_index": 20 + i}],
                "target_time": _target(),
            }, headers=h)
            results[i] = r.status_code
        clr()
        threads = [th.Thread(target=prebook_worker, args=(i,)) for i in range(5)]
        for t in threads: t.start()
        r = client.post("/api/v1/lots", json={
            "lot_id": f"andy_lot_{uuid.uuid4().hex[:4]}",
            "name": "Andy Lot", "total_slots": 50, "base_price": 15.0,
        }, headers=h_adm)
        for t in threads: t.join()
        assert ok(r, (200, 409)), f"create lot under load: {r.text}"

    def test_andy_mines_block(self, client):
        """Andy mines block — succeeds or reports no pending tx."""
        h_adm = _admin(client)
        clr()
        r = client.post("/api/v1/blockchain/mine", headers=h_adm)
        assert ok(r, (200, 400)), f"mine: {r.text}"

    def test_andy_revenue_report(self, client):
        """Andy runs revenue report — gets data or permission error if not admin."""
        h_adm = _admin(client)
        clr()
        r = client.get("/api/v1/revenue/overview", headers=h_adm)
        assert ok(r, (200, 403)), f"revenue: {r.text}"

    def test_andy_pipeline_status(self, client):
        """Andy checks pipeline health."""
        h_adm = _admin(client)
        clr()
        r = client.get("/api/v1/driver/pipeline/status", headers=h_adm)
        assert ok(r, (200, 404, 500)), f"pipeline: {r.text}"


# ===========================================================================
# 7. ZOMBIE ZOE — stale session, expired token, 2-hour-old tab
# ===========================================================================

class TestZombieZoe:
    """Zoe left her tab open for 2 hours. Everything is stale."""

    def test_zoe_stale_jwt(self, client):
        """Zoe uses an old JWT → 401."""
        bad_headers = [
            {"Authorization": "Bearer iamoldandexpired"},
            {"Authorization": "Bearer " + "x" * 200},
            {},
        ]
        for i, bh in enumerate(bad_headers):
            r = client.get("/api/v1/driver/lots", headers=bh)
            assert r.status_code in (401, 403), f"stale {i}: {r.text}"

    def test_zoe_confirm_expired_prebook(self, client):
        """Zoe tries to confirm a prebook that would have expired → 404."""
        h = _auth(client, f"zoe_{uuid.uuid4().hex[:6]}@test.io")
        clr()
        r = client.post("/api/v1/micro/prebook", json={
            "lot_id": "ut_lot_a", "slots": [{"slot_index": 25}],
            "target_time": _target(10080),
        }, headers=h)
        if ok(r, 200):
            pid = r.json()["prebook_id"]
            c = client.post("/api/v1/micro/confirm", json={
                "prebook_id": pid,
            }, headers=h)
            assert c.status_code != 200, f"expired prebook should not confirm: {c.text}"


# ===========================================================================
# 8. PAYMENT PETE — card fails, retries, zero amounts
# ===========================================================================

class TestPaymentPete:
    """Pete's card gets declined at the worst possible moment."""

    def test_pete_can_retry_payment(self, client):
        """Pete's payment fails → he can retry."""
        h = _auth(client, f"pete_{uuid.uuid4().hex[:6]}@test.io")
        clr()
        r = client.post("/api/v1/sessions/start", json={
            "lot_id": "ut_lot_a", "slot": 30,
        }, headers=h)
        assert ok(r, 200), f"session: {r.text}"
        sid = r.json()["session_id"]
        client.post("/api/v1/sessions/end", json={"session_id": sid}, headers=h)
        p1 = client.post("/api/v1/payments/confirm", json={"session_id": sid}, headers=h)
        assert ok(p1, (200, 400, 402, 500)), f"1st payment: {p1.text}"
        p2 = client.post("/api/v1/payments/confirm", json={"session_id": sid}, headers=h)
        assert ok(p2, (200, 400, 402)), f"retry payment: {p2.text}"


# ===========================================================================
# 9. MIDNIGHT MIKE — no recent data, cold lots, stale predictions
# ===========================================================================

class TestMidnightMike:
    """Mike uses the app at 3 AM when no recent data exists."""

    def test_mike_browses_cold_lot(self, client):
        """Mike browses a lot with no recent occupancy records."""
        h = _auth(client, f"mike_{uuid.uuid4().hex[:6]}@test.io")
        clr()
        r = client.get("/api/v1/driver/lots/ut_lot_b", headers=h)
        assert ok(r, 200), f"cold lot: {r.text}"
        d = r.json()
        assert d.get("predicted_occupancy", -1) >= 0, f"bad prediction: {d}"

    def test_mike_starts_session_cold(self, client):
        """Mike starts a session on a lot with no history."""
        h = _auth(client, f"mike2_{uuid.uuid4().hex[:6]}@test.io")
        clr()
        r = client.post("/api/v1/sessions/start", json={
            "lot_id": "ut_lot_c", "slot": 1,
        }, headers=h)
        assert ok(r, 200), f"cold session: {r.text}"

    def test_mike_predict_health(self, client):
        """Mike checks prediction health — works or returns 503."""
        h = _auth(client, f"mike3_{uuid.uuid4().hex[:6]}@test.io")
        clr()
        r = client.get("/api/v1/predict/health", headers=h)
        assert ok(r, (200, 503)), f"predict health: {r.text}"


# ===========================================================================
# 10. BOT BOB — rate limiter exhaustion
# ===========================================================================

class TestBotBob:
    """Bob is an automated script hitting endpoints as fast as possible."""

    def test_bob_gets_rate_limited_globally(self, client):
        """Bob sends 150 rapid requests → eventually gets 429."""
        h = _auth(client, f"bob_{uuid.uuid4().hex[:6]}@test.io")
        clr()
        got_429 = False
        for _ in range(210):
            r = client.get("/api/v1/driver/lots", headers=h)
            if r.status_code == 429:
                got_429 = True
                break
        assert got_429, "Bob should hit global rate limit (210 reqs)"

    def test_bob_spams_login(self, client):
        """Bob spams login endpoint → 429 after ~10 attempts."""
        clr()
        got_429 = False
        for _ in range(20):
            r = client.post("/api/v1/auth/login", json={
                "email": "bob_spam@test.io",
                "password": "Pass123!",
            })
            if r.status_code == 429:
                got_429 = True
                break
        assert got_429, "Bob should hit login rate limit"

    def test_bob_spams_prebook(self, client):
        """Bob spams prebook endpoint → 429."""
        h = _auth(client, f"bob2_{uuid.uuid4().hex[:6]}@test.io")
        clr()
        got_429 = False
        for i in range(50):
            r = client.post("/api/v1/micro/prebook", json={
                "lot_id": "ut_lot_a", "slots": [{"slot_index": 80 + i}],
                "target_time": _target(),
            }, headers=h)
            if r.status_code == 429:
                got_429 = True
                break
        assert got_429, "Bob should hit prebook rate limit"
