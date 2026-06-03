"""Exhaustive feature test against live Render API."""
import requests, json, sys, time, uuid

BASE = "https://pragma-4szs.onrender.com"
passed, failed, skipped = 0, 0, 0

def test(name, fn):
    global passed, failed, skipped
    try:
        fn()
        passed += 1
        print(f"  PASS  {name}")
    except AssertionError as e:
        failed += 1
        print(f"  FAIL  {name}: {e}")
    except requests.exceptions.HTTPError as e:
        # Check if it's a cold-start HTML response vs real API error
        try:
            resp = e.response
            ct = resp.headers.get("content-type","")
            if "text/html" in ct:
                skipped += 1
                print(f"  SKIP  {name}: HTML response (cold start?)")
            else:
                failed += 1
                print(f"  FAIL  {name}: HTTP {resp.status_code} - {resp.text[:200]}")
        except:
            failed += 1
            print(f"  FAIL  {name}: {e}")
    except Exception as e:
        failed += 1
        print(f"  FAIL  {name}: {e}")

def assert_ok(r, msg=""):
    ct = r.headers.get("content-type","")
    if "text/html" in ct:
        raise AssertionError(f"HTML response instead of JSON: {r.text[:200]}")
    assert r.ok, f"HTTP {r.status_code}: {r.text[:300]}"
    j = r.json()
    return j

def assert_in(key, obj, msg=""):
    assert key in obj, f"Missing key '{key}' in {list(obj.keys())}" + (f": {msg}" if msg else "")

# --- Login once ---
def do_login():
    r = requests.post(f"{BASE}/api/v1/auth/login", json={"email": "admin@pragma.io", "password": "admin123"}, timeout=30)
    j = assert_ok(r)
    assert "access_token" in j
    return j["access_token"]

token = None
def get_token():
    global token
    if not token:
        token = do_login()
    return token

def auth_h(token=None):
    return {"Authorization": f"Bearer {token or get_token()}"}

print("="*60)
print("PRAGMAPARK LIVE API FEATURE TESTS")
print(f"Target: {BASE}")
print("="*60)

# ===== 1. AUTH =====
print("\n--- 1. AUTH ---")

def t_auth_login():
    r = requests.post(f"{BASE}/api/v1/auth/login", json={"email": "admin@pragma.io", "password": "admin123"}, timeout=30)
    j = assert_ok(r)
    assert_in("access_token", j)
    assert_in("user", j)
    assert j["user"]["email"] == "admin@pragma.io"
test("POST /auth/login (admin)", t_auth_login)

def t_auth_login_driver():
    r = requests.post(f"{BASE}/api/v1/auth/login", json={"email": "driver@test.com", "password": "driver123"}, timeout=30)
    j = assert_ok(r)
    assert j["user"]["role"] == "driver"
test("POST /auth/login (driver)", t_auth_login_driver)

def t_auth_login_bad():
    r = requests.post(f"{BASE}/api/v1/auth/login", json={"email": "bad@x.com", "password": "wrong"}, timeout=30)
    assert r.status_code in (401, 403, 422)
test("POST /auth/login (bad creds)", t_auth_login_bad)

def t_auth_me():
    r = requests.get(f"{BASE}/api/v1/auth/me", headers=auth_h(), timeout=30)
    j = assert_ok(r)
    assert j["email"] == "admin@pragma.io"
test("GET /auth/me", t_auth_me)

def t_auth_register():
    uid = uuid.uuid4().hex[:8]
    r = requests.post(f"{BASE}/api/v1/auth/register", json={"email": f"test_{uid}@test.com", "password": "test123", "full_name": "Test User"}, timeout=30)
    j = assert_ok(r)
    assert_in("access_token", j)
test("POST /auth/register", t_auth_register)

# ===== 2. PARKING LOTS =====
print("\n--- 2. PARKING LOTS ---")

def t_lots_list():
    r = requests.get(f"{BASE}/api/v1/lots", headers=auth_h(), timeout=30)
    j = assert_ok(r)
    assert len(j) >= 20, f"Expected >=20 lots, got {len(j)}"
    assert_in("lot_id", j[0])
    assert_in("name", j[0])
    assert_in("city", j[0])
test("GET /lots (list, 20+)", t_lots_list)

def t_lots_city_filter():
    r = requests.get(f"{BASE}/api/v1/lots?city=London", headers=auth_h(), timeout=30)
    j = assert_ok(r)
    for lot in j:
        assert lot["city"] == "London", f"Expected London, got {lot['city']}"
test("GET /lots (city filter)", t_lots_city_filter)

def t_lots_detail():
    r = requests.get(f"{BASE}/api/v1/lots/London01", headers=auth_h(), timeout=30)
    j = assert_ok(r)
    assert j["lot_id"] == "London01"
    assert_in("total_slots", j)
    assert_in("base_price", j)
    assert_in("history", j)
    assert len(j["history"]) > 0
test("GET /lots/{id} (detail)", t_lots_detail)

def t_lots_occupancy():
    r = requests.get(f"{BASE}/api/v1/lots/London01/occupancy?hours=24", headers=auth_h(), timeout=30)
    j = assert_ok(r)
    assert len(j["records"]) > 0
    assert_in("occupied_slots", j["records"][0])
    assert_in("total_slots", j["records"][0])
test("GET /lots/{id}/occupancy", t_lots_occupancy)

def t_lots_owner():
    r = requests.get(f"{BASE}/api/v1/lots/owner", headers=auth_h(), timeout=30)
    assert_ok(r)
test("GET /lots/owner", t_lots_owner)

def t_lots_post():
    uid = uuid.uuid4().hex[:6]
    r = requests.post(f"{BASE}/api/v1/lots", headers=auth_h(), json={"lot_id": f"TEST{uid}", "name": f"Test Lot {uid}", "total_slots": 50, "base_price": 2.5, "address": "123 Test St", "city": "TestCity"}, timeout=30)
    j = assert_ok(r)
    assert j["status"] == "ok"
test("POST /lots (create)", t_lots_post)

def t_lots_config():
    r = requests.put(f"{BASE}/api/v1/lots/London01/config", headers=auth_h(), json={"name": "London Updated"}, timeout=30)
    j = assert_ok(r)
    assert j["status"] == "ok"
test("PUT /lots/{id}/config", t_lots_config)

# ===== 3. DRIVER =====
print("\n--- 3. DRIVER ---")

dtoken = None
def driver_token():
    global dtoken
    if not dtoken:
        r = requests.post(f"{BASE}/api/v1/auth/login", json={"email": "driver@test.com", "password": "driver123"}, timeout=30)
        dtoken = assert_ok(r)["access_token"]
    return dtoken

def t_driver_lots():
    r = requests.get(f"{BASE}/api/v1/driver/lots", headers=auth_h(driver_token()), timeout=30)
    j = assert_ok(r)
    assert_in("lots", j)
    assert len(j["lots"]) > 0
    lot = j["lots"][0]
    assert_in("lot_id", lot)
    assert_in("name", lot)
    assert_in("predicted_occupancy", lot)
    assert_in("available_spots", lot)
    assert_in("dynamic_price", lot)
test("GET /driver/lots", t_driver_lots)

def t_driver_lots_detail():
    r = requests.get(f"{BASE}/api/v1/driver/lots/London01", headers=auth_h(driver_token()), timeout=30)
    j = assert_ok(r)
    assert_in("lot_id", j)
    assert_in("recent_occupancy", j)
    assert_in("predicted_occupancy", j)
test("GET /driver/lots/{id}", t_driver_lots_detail)

def t_driver_filtered():
    r = requests.get(f"{BASE}/api/v1/driver/lots?slot_type=ev&max_price=5.0", headers=auth_h(driver_token()), timeout=30)
    assert_ok(r)
test("GET /driver/lots (filtered EV<5)", t_driver_filtered)

def t_driver_pipeline():
    r = requests.get(f"{BASE}/api/v1/driver/pipeline/status", headers=auth_h(driver_token()), timeout=30)
    j = assert_ok(r)
    assert_in("ml_models", j)
    assert_in("rl_agent", j)
test("GET /driver/pipeline/status", t_driver_pipeline)

# ===== 4. PREDICTIONS (ML) =====
print("\n--- 4. PREDICTIONS (ML) ---")

def t_pred_occupancy():
    r = requests.post(f"{BASE}/api/v1/predict/occupancy", headers=auth_h(), json={"occupied_slots": 60, "total_slots": 100, "occ_lag_15m": 55, "occ_lag_1h": 45, "net_flux": 5, "hour": 14}, timeout=30)
    j = assert_ok(r)
    assert_in("rf_prediction", j)
    assert_in("xgb_prediction", j)
    assert_in("ensemble_prediction", j)
    for k in ["rf_prediction", "xgb_prediction", "ensemble_prediction"]:
        assert isinstance(j[k], (int, float)), f"{k} not a number: {j[k]}"
test("POST /predict/occupancy (ensemble)", t_pred_occupancy)

def t_pred_health():
    r = requests.get(f"{BASE}/api/v1/predict/health", headers=auth_h(), timeout=30)
    j = assert_ok(r)
    assert j["rf_loaded"] in (True, False)
    assert j["xgb_loaded"] in (True, False)
    assert_in("status", j)
test("GET /predict/health", t_pred_health)

# ===== 5. PRICING (RL) =====
print("\n--- 5. PRICING (RL) ---")

def t_pricing_adjust():
    r = requests.post(f"{BASE}/api/v1/pricing/adjust", headers=auth_h(), json={"predicted_occupancy": 0.75, "current_price": 5.0}, timeout=30)
    j = assert_ok(r)
    assert_in("price_multiplier", j)
    assert_in("new_price", j)
    assert_in("is_hike", j)
test("POST /pricing/adjust", t_pricing_adjust)

def t_pricing_zones():
    r = requests.get(f"{BASE}/api/v1/pricing/zones", headers=auth_h(), timeout=30)
    j = assert_ok(r)
    assert_in("zone_id", j)
test("GET /pricing/zones", t_pricing_zones)

# ===== 6. BLOCKCHAIN =====
print("\n--- 6. BLOCKCHAIN ---")

def t_bc_status():
    r = requests.get(f"{BASE}/api/v1/blockchain/status", headers=auth_h(), timeout=30)
    j = assert_ok(r)
    assert_in("chain_length", j)
    assert j["chain_length"] >= 1
    assert_in("chain_valid", j)
    assert_in("pending_transactions", j)
test("GET /blockchain/status", t_bc_status)

def t_bc_transaction():
    r = requests.post(f"{BASE}/api/v1/blockchain/transaction", headers=auth_h(driver_token()), json={"driver_id": "driver@test.com", "lot_id": "London01", "action": "session_fee", "price": 5.0, "duration_minutes": 60}, timeout=30)
    j = assert_ok(r)
    assert_in("tx_hash", j)
    assert_in("block_index", j)
test("POST /blockchain/transaction", t_bc_transaction)

def t_bc_mine():
    r = requests.post(f"{BASE}/api/v1/blockchain/mine", headers=auth_h(), timeout=30)
    j = assert_ok(r)
    assert_in("block_index", j)
    assert_in("hash", j)
test("POST /blockchain/mine", t_bc_mine)

def t_bc_pool_create():
    pid = "POOL" + uuid.uuid4().hex[:4]
    r = requests.post(f"{BASE}/api/v1/blockchain/pool/create", headers=auth_h(), json={"pool_id": pid, "total_spots": 30}, timeout=30)
    j = assert_ok(r)
    assert j["status"] == "ok"
test("POST /blockchain/pool/create", t_bc_pool_create)

def t_bc_pool_get():
    r = requests.get(f"{BASE}/api/v1/blockchain/pool/Pool01", headers=auth_h(), timeout=30)
    j = assert_ok(r)
    assert_in("pool_id", j)
test("GET /blockchain/pool/{id}", t_bc_pool_get)

# ===== 7. DIGITAL TWIN =====
print("\n--- 7. DIGITAL TWIN ---")

def t_dt_scenarios():
    r = requests.get(f"{BASE}/api/v1/digital-twin/scenarios", headers=auth_h(), timeout=30)
    j = assert_ok(r)
    assert len(j) > 0, "Expected >0 scenarios"
test("GET /digital-twin/scenarios", t_dt_scenarios)

def t_dt_scenario():
    r = requests.post(f"{BASE}/api/v1/digital-twin/scenario", headers=auth_h(), json={"scenario_type": "zone_closure"}, timeout=30)
    j = assert_ok(r)
    assert_in("scenario", j)
    assert_in("result", j)
test("POST /digital-twin/scenario", t_dt_scenario)

def t_dt_generate():
    r = requests.post(f"{BASE}/api/v1/digital-twin/generate", headers=auth_h(), json={"base_occupancy": 0.5, "base_price": 5.0}, timeout=30)
    j = assert_ok(r)
    assert_in("synthetic_occupancy", j)
test("POST /digital-twin/generate", t_dt_generate)

# ===== 8. MARL =====
print("\n--- 8. MARL ---")

def t_marl_status():
    r = requests.get(f"{BASE}/api/v1/marl/status", headers=auth_h(), timeout=30)
    j = assert_ok(r)
    assert_in("status", j)
test("GET /marl/status", t_marl_status)

def t_marl_train():
    r = requests.post(f"{BASE}/api/v1/marl/train", headers=auth_h(), json={"num_zones": 2, "episodes": 5}, timeout=120)
    j = assert_ok(r)
    assert j["status"] == "ok"
    assert_in("final_reward", j)
test("POST /marl/train", t_marl_train)

# ===== 9. SESSIONS =====
print("\n--- 9. SESSIONS ---")

dt = driver_token()

def t_session_start():
    r = requests.post(f"{BASE}/api/v1/sessions/start", headers=auth_h(dt), json={"lot_id": "London01", "slot": "A1", "payment_method": "card"}, timeout=30)
    j = assert_ok(r)
    assert_in("session_id", j)
    assert_in("lot_id", j)
    assert_in("price_at_entry", j)
    assert_in("blockchain_ref", j)
    return j["session_id"]
session_id = None
def run_t_session_start():
    global session_id
    session_id = t_session_start()
test("POST /sessions/start", run_t_session_start)

def t_session_detail():
    global session_id
    if not session_id:
        session_id = t_session_start()
    r = requests.get(f"{BASE}/api/v1/sessions/{session_id}", headers=auth_h(dt), timeout=30)
    j = assert_ok(r)
    assert_in("session_id", j)
test(f"GET /sessions/{{id}}", t_session_detail)

def t_session_pricing():
    global session_id
    if not session_id:
        session_id = t_session_start()
    r = requests.get(f"{BASE}/api/v1/sessions/{session_id}/pricing", headers=auth_h(dt), timeout=30)
    j = assert_ok(r)
    assert_in("base_price", j)
    assert_in("pricing_formula", j)
test(f"GET /sessions/{{id}}/pricing", t_session_pricing)

def t_session_end():
    global session_id
    if not session_id:
        session_id = t_session_start()
    time.sleep(2)  # quick session
    r = requests.post(f"{BASE}/api/v1/sessions/end", headers=auth_h(dt), json={"session_id": session_id}, timeout=30)
    j = assert_ok(r)
    assert_in("total_charged", j)
    assert_in("deposit_refund", j)
test("POST /sessions/end", t_session_end)

def t_session_history():
    r = requests.get(f"{BASE}/api/v1/sessions/history", headers=auth_h(dt), timeout=30)
    j = assert_ok(r)
    assert_in("total_sessions", j)
    assert_in("sessions", j)
test("GET /sessions/history", t_session_history)

def t_session_active():
    r = requests.get(f"{BASE}/api/v1/sessions/active/London01", headers=auth_h(dt), timeout=30)
    j = assert_ok(r)
    assert_in("lot_id", j)
    assert_in("active_count", j)
test("GET /sessions/active/{lot_id}", t_session_active)

# ===== 10. PAYMENTS =====
print("\n--- 10. PAYMENTS ---")

def t_payments_history():
    r = requests.get(f"{BASE}/api/v1/payments/history", headers=auth_h(dt), timeout=30)
    j = assert_ok(r)
    assert_in("total_payments", j)
    assert_in("payments", j)
test("GET /payments/history", t_payments_history)

def t_payment_confirm():
    global session_id
    if not session_id:
        session_id = t_session_start()
    time.sleep(1)
    # First end the session
    try:
        requests.post(f"{BASE}/api/v1/sessions/end", headers=auth_h(dt), json={"session_id": session_id}, timeout=30)
    except:
        pass
    r = requests.post(f"{BASE}/api/v1/payments/confirm", headers=auth_h(dt), json={"session_id": session_id, "idempotency_key": f"test_{session_id}"}, timeout=30)
    j = assert_ok(r)
test("POST /payments/confirm", t_payment_confirm)

# ===== 11. MICRO SLOTS =====
print("\n--- 11. MICRO SLOTS ---")

def t_micro_slots():
    r = requests.get(f"{BASE}/api/v1/micro/lots/London01/slots", headers=auth_h(), timeout=30)
    j = assert_ok(r)
    assert_in("lot_id", j)
    assert_in("total_slots", j)
    assert_in("slots", j)
    assert len(j["slots"]) > 0
    slot = j["slots"][0]
    assert_in("slot_index", slot)
    assert_in("state", slot)
    assert_in("price_modifier", slot)
test("GET /micro/lots/{id}/slots", t_micro_slots)

def t_micro_zones():
    r = requests.get(f"{BASE}/api/v1/micro/lots/London01/zones", headers=auth_h(), timeout=30)
    j = assert_ok(r)
    assert len(j) > 0
    assert_in("id", j[0])
    assert_in("name", j[0])
test("GET /micro/lots/{id}/zones", t_micro_zones)

def t_micro_probability():
    r = requests.get(f"{BASE}/api/v1/micro/lots/London01/slots/0/probability", headers=auth_h(), timeout=30)
    j = assert_ok(r)
    assert_in("slot_id", j)
    assert_in("probability", j)
test("GET /micro/lots/{id}/slots/{idx}/probability", t_micro_probability)

def t_micro_reserve():
    r = requests.post(f"{BASE}/api/v1/micro/reserve", headers=auth_h(dt), json={"lot_id": "London01", "slot_index": 5}, timeout=30)
    j = assert_ok(r)
    assert_in("reservation_id", j)
    assert_in("expires_at", j)
    return j
reservation = {}
def run_t_micro_reserve():
    global reservation
    reservation = t_micro_reserve()
test("POST /micro/reserve", run_t_micro_reserve)

def t_micro_release():
    global reservation
    if not reservation:
        reservation = t_micro_reserve()
    r = requests.post(f"{BASE}/api/v1/micro/release", headers=auth_h(dt), json={"slot_id": f"London01-{reservation.get('slot_id','')}", "reservation_id": reservation.get("reservation_id","")}, timeout=30)
    j = assert_ok(r)
    assert j["status"] == "ok"
test("POST /micro/release", t_micro_release)

def t_micro_prebook():
    r = requests.post(f"{BASE}/api/v1/micro/prebook", headers=auth_h(dt), json={"lot_id": "London01", "slots": [{"slot_index": 10, "priority": 1}], "target_time": (time.time() + 3600)}, timeout=30)
    j = assert_ok(r)
    assert_in("prebook_id", j)
    assert_in("expires_at", j)
    return j
prebook = {}
def run_t_micro_prebook():
    global prebook
    prebook = t_micro_prebook()
test("POST /micro/prebook", run_t_micro_prebook)

def t_micro_prebooks_list():
    r = requests.get(f"{BASE}/api/v1/micro/prebooks/list", headers=auth_h(dt), timeout=30)
    j = assert_ok(r)
test("GET /micro/prebooks/list", t_micro_prebooks_list)

# ===== 12. WALLET =====
print("\n--- 12. WALLET ---")

def t_wallet_get():
    r = requests.get(f"{BASE}/api/v1/wallet", headers=auth_h(dt), timeout=30)
    j = assert_ok(r)
    assert_in("balance", j)
test("GET /wallet", t_wallet_get)

def t_wallet_topup():
    r = requests.post(f"{BASE}/api/v1/wallet/topup", headers=auth_h(dt), json={"amount": 20.0}, timeout=30)
    j = assert_ok(r)
    assert_in("balance", j)
    assert_in("amount_added", j)
    assert j["amount_added"] == 20.0
test("POST /wallet/topup", t_wallet_topup)

# ===== 13. REVENUE =====
print("\n--- 13. REVENUE ---")

def t_revenue_cumulative():
    r = requests.get(f"{BASE}/api/v1/revenue/cumulative", headers=auth_h(), timeout=30)
    j = assert_ok(r)
    assert_in("total_revenue", j)
    assert_in("total_sessions", j)
    assert_in("total_lots", j)
test("GET /revenue/cumulative", t_revenue_cumulative)

def t_revenue_overview():
    r = requests.get(f"{BASE}/api/v1/revenue/overview?days=7", headers=auth_h(), timeout=30)
    j = assert_ok(r)
    assert_in("total_revenue", j)
    assert_in("daily", j)
test("GET /revenue/overview", t_revenue_overview)

def t_revenue_transactions():
    r = requests.get(f"{BASE}/api/v1/revenue/transactions", headers=auth_h(), timeout=30)
    j = assert_ok(r)
    assert len(j) >= 0
test("GET /revenue/transactions", t_revenue_transactions)

# ===== 14. ADMIN =====
print("\n--- 14. ADMIN ---")

def t_admin_dashboard():
    r = requests.get(f"{BASE}/api/v1/admin/dashboard", headers=auth_h(), timeout=30)
    j = assert_ok(r)
    assert_in("total_lots", j)
    assert_in("total_users", j)
    assert_in("total_revenue", j)
    assert_in("system_occupancy", j)
test("GET /admin/dashboard", t_admin_dashboard)

def t_admin_health():
    r = requests.get(f"{BASE}/api/v1/admin/system-health", headers=auth_h(), timeout=30)
    j = assert_ok(r)
    assert j["status"] == "operational"
    assert_in("layers", j)
    for layer in ["iot", "ml", "blockchain", "rl", "digital_twin", "api"]:
        assert layer in j["layers"], f"Missing layer: {layer}"
test("GET /admin/system-health", t_admin_health)

# ===== 15. INGESTION =====
print("\n--- 15. INGESTION ---")

def t_ingestion():
    r = requests.post(f"{BASE}/api/v1/ingestion/occupancy", headers=auth_h(), json={"lot_id": "London01", "occupied_slots": 45, "total_slots": 100, "net_flux": 3}, timeout=30)
    j = assert_ok(r)
    assert_in("lot_id", j)
    assert_in("occupancy_rate", j)
test("POST /ingestion/occupancy", t_ingestion)

# ===== 16. SIMULATION =====
print("\n--- 16. SIMULATION ---")

def t_sim_status():
    r = requests.get(f"{BASE}/api/v1/simulation/status", headers=auth_h(), timeout=30)
    j = assert_ok(r)
    assert_in("speedup", j)
    assert_in("is_fast_forwarding", j)
test("GET /simulation/status", t_sim_status)

def t_sim_speed():
    r = requests.post(f"{BASE}/api/v1/simulation/speed", headers=auth_h(), json={"speedup": 10}, timeout=30)
    assert r.ok
test("POST /simulation/speed", t_sim_speed)

# ===== 17. HEALTH / READY =====
print("\n--- 17. HEALTH ---")

def t_health():
    r = requests.get(f"{BASE}/api/v1/health", timeout=30)
    j = assert_ok(r)
    assert j["status"] == "ok"
    assert_in("layers", j)
test("GET /health (unauthenticated)", t_health)

def t_ready():
    r = requests.get(f"{BASE}/api/v1/ready", timeout=30)
    j = assert_ok(r)
    assert j["ready"] in (True, False)
test("GET /ready (unauthenticated)", t_ready)

def t_openapi():
    r = requests.get(f"{BASE}/openapi.json", timeout=30)
    j = assert_ok(r)
    assert_in("paths", j)
    assert len(j["paths"]) >= 60
test("GET /openapi.json (60+ paths)", t_openapi)

# ===== 18. DRIVER FULL FLOW INTEGRATION =====
print("\n--- 18. DRIVER FULL FLOW ---")

def t_full_driver_flow():
    tok = driver_token()
    # 1. Find a lot
    r = requests.get(f"{BASE}/api/v1/driver/lots", headers=auth_h(tok), timeout=30)
    lots = assert_ok(r)["lots"]
    assert len(lots) > 0
    lot_id = lots[0]["lot_id"]
    
    # 2. View lot detail + slots
    r = requests.get(f"{BASE}/api/v1/driver/lots/{lot_id}", headers=auth_h(tok), timeout=30)
    detail = assert_ok(r)
    assert_in("lot_id", detail)
    
    # 3. View slot grid
    r = requests.get(f"{BASE}/api/v1/micro/lots/{lot_id}/slots", headers=auth_h(tok), timeout=30)
    slots = assert_ok(r)
    assert slots["total_slots"] > 0
    
    # 4. Reserve a slot
    r = requests.post(f"{BASE}/api/v1/micro/reserve", headers=auth_h(tok), json={"lot_id": lot_id, "slot_index": 3}, timeout=30)
    res = assert_ok(r)
    
    # 5. Start session
    r = requests.post(f"{BASE}/api/v1/sessions/start", headers=auth_h(tok), json={"lot_id": lot_id, "slot": "A1", "payment_method": "card"}, timeout=30)
    sess = assert_ok(r)
    sess_id = sess["session_id"]
    
    # 6. Check wallet
    r = requests.get(f"{BASE}/api/v1/wallet", headers=auth_h(tok), timeout=30)
    wallet = assert_ok(r)
    
    # 7. Check session pricing
    r = requests.get(f"{BASE}/api/v1/sessions/{sess_id}/pricing", headers=auth_h(tok), timeout=30)
    pricing = assert_ok(r)
    
    # 8. End session
    time.sleep(2)
    r = requests.post(f"{BASE}/api/v1/sessions/end", headers=auth_h(tok), json={"session_id": sess_id}, timeout=30)
    ended = assert_ok(r)
    
    # 9. Confirm payment
    r = requests.post(f"{BASE}/api/v1/payments/confirm", headers=auth_h(tok), json={"session_id": sess_id, "idempotency_key": f"flow_{sess_id}"}, timeout=30)
    pay = assert_ok(r)
    
    # 10. Check receipt / history
    r = requests.get(f"{BASE}/api/v1/sessions/history", headers=auth_h(tok), timeout=30)
    hist = assert_ok(r)
    
    # 11. Wallet post-session
    r = requests.get(f"{BASE}/api/v1/wallet", headers=auth_h(tok), timeout=30)
    assert_ok(r)
    
    print(f"    Full flow: {lot_id} → session {sess_id} → settled")
test("DRIVER FULL FLOW (10-step)", t_full_driver_flow)

# ===== SUMMARY =====
print("\n" + "="*60)
print(f"RESULTS: {passed} passed, {failed} failed, {skipped} skipped")
print("="*60)
sys.exit(0 if failed == 0 else 1)
