# Workflow Trace Journal

> Comprehensive UI→API→Backend→DB trace for every workflow in the Pragma Smart Parking system.
> Generated: 2026-06-08

---

## PHASE 0: WARMUP & DATA LAYER

### WF#0 WarmupContext (System Ready Polling)
**Frontend**: `WarmupContext.tsx`
- Mount → starts polling `GET /health` every 8s, up to 75 attempts (10 min timeout)
- On health success (200): calls `POST /auth/login` auto-login as admin (`admin@pragma.io` / `admin123`) via adminClient
- Sets `backendReady: boolean` in context → all landing page components read this to decide live vs fallback
- Tracks `backendChecking` / `backendError`

**Backend**: `GET /health` → server.py health endpoint
- Returns `{"status": "ok", "timestamp": ...}`
- No auth required, no DB query

**Response**: 200 with JSON status
**UI Rendering**: `backendReady=true` → components use real API; `backendReady=false` → fallback/simulation mode

---

## PHASE 1: AUTHENTICATION (WF#1-WF#4)

### WF#1 Admin Login
**Frontend**: `LoginPage.tsx` → `AuthContext.login(email, password)` → `adminClient.loginUser()`
- Pre-filled defaults: `admin@pragma.io` / `admin123` if inputs empty
- On submit: calls `POST /auth/login`

**Backend**: `auth.py:69-87` → `POST /auth/login`
Branches:
1. **Rate limiter (IP) check** → FAIL → `429 Too Many Requests`
2. **Rate limiter (account) check** → FAIL → `429 Too Many Requests`
3. **User not found** (`query User by email` → None) → `401 Invalid credentials`
4. **Password mismatch** (`verify_password` fails) → `401 Invalid credentials`
5. **Success**: create JWT (60min expiry, sub=email, role=user.role)
   - Set cookie: `pragma_token=<JWT>`; HttpOnly, secure=production, samesite=lax
   - Return `AuthResponse(access_token, user={id, email, full_name, role, organization})`

**Frontend rendering**:
- **Success**: `AuthContext` stores user; checks `user.role`:
  - role==='admin' → `window.location.hash = '#/app/dashboard'`
  - role==='driver' → `window.location.hash = '/driver/dashboard'`
- **Failure**: catches error → sets `localError` state; error banner shown in form

### WF#2 Driver Login
**Frontend**: `DriverLoginPage.tsx` → `AuthContext.login()` → shared `POST /auth/login`
- If already authenticated **and** role==='driver' → redirect immediately to `/driver/dashboard` (line 28-31)
- Default credentials: `driver@pragma.io` / `driver123` (pre-filled if inputs empty)

**Backend**: Same as WF#1 (shared `/auth/login` endpoint)

**Frontend rendering**:
- Same as WF#1 but with different redirect path (/driver/dashboard)

### WF#3 Auth Check (GET /auth/me)
**Frontend**: `AuthContext.tsx` mount → `loginUser()` → `GET /auth/me`
- Cookie sent via `withCredentials: true`

**Backend**: `auth.py:59-71` (get_current_user_from_cookie_or_header), `auth.py:89-101`
Resolution order:
1. Read `pragma_token` cookie OR `Authorization: Bearer` header
2. No token → 401 "Not authenticated"
3. JWT decode (HS256):
   - Invalid signature → 401 "Invalid token"
   - **Expired** (`exp < now`) → 401 "Token expired"
   - Role not 'admin' or 'driver' → 401 "Invalid token"
4. Check `TokenBlacklist` — if token blacklisted → 401 (effectively)

**Success** → return user dict: `{id, email, full_name, role, sub}`
**Frontend rendering**:
- Success → `setUser(data)` in AuthContext; guards pass
- 401 → `setUser(null)`, `loading=false` → AdminGuard/DriverGuard sees `!isAuthenticated` → redirect to `/login`

### WF#4 Logout
**Frontend**: `AuthContext.logout()` → `adminClient.logoutUser()` → `POST /auth/logout`

**Backend**: `auth.py:108-117`
- `get_current_user` reads JWT from cookie
- Extracts `jti` (JWT ID)
- Inserts into `TokenBlacklist(invalidated_at=now)` via DB
- Response clears cookie: `pragma_token=; Max-Age=0; Path=/`

**Frontend rendering**: user set to null in AuthContext → Guards redirect to `/login`

---

## PHASE 2: LOTS & PARKING (WF#5-WF#9)

### WF#5 Public Lots Listing (Landing / Admin)
**Frontend**: `adminClient.fetchLots()` → `GET /lots`

**Backend**: `lots.py:15-28` → `GET /api/v1/lots`
- Optional `city` query param filter
- Pagination: `offset` (default 0), `limit` (default 100, max 1000)
- Query: `ParkingLot.query.order_by(lot_id).offset(offset).limit(limit)`
- For each lot: `get_latest_occupancies(session, lot_ids)` → subquery of latest `OccupancyRecord` per lot
- `lot_to_summary()` utility builds LotSummary with current_occupancy, available_slots, etc.

**Response**: `List[LotSummary]`
**No auth required** (public endpoint)
**UI Rendering**: Landing page uses this (via WarmupContext's backendReady) for Hero/MetricTicker

### WF#6 Admin Lots Detail
**Frontend**: `adminClient.fetchLotDetail(lotId)` → `GET /lots/{lot_id}`

**Backend**: `lots.py:129-156` → `GET /api/v1/lots/{lot_id}`
- Query `ParkingLot` by lot_id → 404 if not found
- Query last 100 `OccupancyRecord` for lot (ordered desc)
- Return `LotDetail` with `history[]` (reversed to chronological)

**Auth required**: JWT (any authenticated user)

### WF#7 Lot Occupancy Data
**Frontend**: `adminClient.fetchOccupancy(lotId, hours)` → `GET /lots/{lot_id}/occupancy?hours=24`

**Backend**: `lots.py:158-188` → `GET /api/v1/lots/{lot_id}/occupancy`
- Validate lot exists (404)
- Calculate cutoff = now - hours (default 24, max 168)
- Latest record for current_occupancy + current_price
- Records within window, ordered by timestamp
- Returns `LotOccupancyResponse(current_occupancy, current_price, records[])`

**No auth required**

### WF#8 Lot Predictions
**Frontend**: Used by `PredictionEngine.tsx` and `lots.py:191-259` endpoint

**Backend**: `lots.py:191-259` → `GET /api/v1/lots/{lot_id}/predictions`
- Auth required
- Validates lot exists (404)
- Fetches OccupancyRecords for last (hours + 3 warmup) hours
- For each record in window:
  - Build 19 features via `build_features_from_records(history_slice, total_slots)`
  - Load RF + XGB + meta models
  - Predict with ensemble (RidgeCV meta-learner, fallback static weights)
  - Clip to [0.0, 1.0]
- Returns `[{timestamp, predicted_occupancy_rate, actual_occupancy_rate}]`
- **Branches**:
  - Models not loaded → 503 "Models not trained/loaded"
  - History too short for features → falls back to raw occupancy_rate
  - Meta model None → uses static RF/XGB weighted average

### WF#9 Create Lot (Admin)
**Frontend**: `adminClient.createLot(data)` → `POST /lots`

**Backend**: `lots.py:30-58` → `POST /api/v1/lots`
- Auth required, `require_admin(user)` → 403 if not admin
- **Branches**:
  - Lot ID already exists → 400 "Lot ID already exists"
  - Missing email in token → 401 "Invalid token: missing subject"
  - User not found in DB → 401 "User not found"
  - Success → create ParkingLot record, commit, return `LotCreateResponse`
  - Any other Exception → 500 "Lot creation failed", rollback

### WF#10 Update Lot Config (Admin/Owner)
**Frontend**: `adminClient.updateLot(lotId, data)` → `PUT /lots/{lot_id}/config`

**Backend**: `lots.py:83-127` → `PUT /api/v1/lots/{lot_id}/config`
- Auth required
- **Branches**:
  - Lot not found → 404
  - Not owner and not admin → 403
  - Partial update: only provided fields changed (price_cap, base_price, name, address, total_slots)
  - Reducing `total_slots` → logs warning if active sessions exist beyond new capacity
  - Success → `LotUpdateResponse(status="updated", base_price, price_cap)`

---

## PHASE 3: DRIVER LOTS & SEARCH (WF#11-WF#13)

### WF#11 Driver Search Lots
**Frontend**: `FindPage.tsx` → `fetchDriverLots(params)` → `GET /driver/lots`

**Backend**: `driver.py:39-65` → `GET /api/v1/driver/lots`
- Auth required (JWT)
- Query all ParkingLots with pagination
- For each lot:
  1. `get_latest_occupancies()` → latest OccupancyRecord
  2. `_batch_slot_type_counts(db, lot_ids)` → queries MicroSlot; checks slot_state_engine per slot for available/handicap/ev/regular counts
  3. `lot_to_summary()` → base summary
  4. `pipeline.driver_search_lots(lots_data)` → orchestrator enriches with ML prediction + RL pricing
- **Filter branches**:
  - `slot_type` param → filter to lots where `available_{slot_type} > 0`
  - `max_price` param → filter to lots where `dynamic_price <= max_price`

**Orchestrator.driver_search_lots** (orchestrator.py:160-199):
1. `_ensure_models()` → lazy-loads predictor + MARL
2. For each lot:
   - Build features Series (19 features with cyclical time + approximations for PE/rolling stats)
   - `_predict_price(features, current_price, price_cap)` → predicted_occ + RL-adjusted price
   - Compute `available_spots = total_slots * (1 - predicted_occ)`
3. Return sorted by available_spots (descending)

**Frontend rendering** (`FindPage.tsx`):
- Loading → "Finding nearby lots..." animation
- Error → yellow banner with "Retry" button
- Empty → "No lots available nearby" with map icon
- Success → lot cards sorted by `dynamic_price` ascending (client-side sort)
  - Each card: name, city, available_spots, dynamic_price, predicted_occupancy bar, actions
  - "Park Here" → navigates to SlotPicker detail view
  - "Reserve" → opens ReserveModal
- Filter pills: All / Regular / Handicap / EV → toggles `slotType` state
- Price range slider (5-150) → sets `maxPrice` state
- When `hasActiveFilters` → shows "Reset" button

### WF#12 Driver Lot Detail
**Frontend**: `FindPage.tsx` → `fetchLotDetail(lotId)` → `GET /driver/lots/{lot_id}`

**Backend**: `driver.py:67-114` → `GET /api/v1/driver/lots/{lot_id}`
- Auth required
- Query ParkingLot → 404 if not found
- Query last 24 OccupancyRecords (desc) for occupancy history
- Batch slot type counts from state engine
- Enrich via `pipeline.driver_search_lots()` for prediction + price
- Returns `DriverLotDetail` with:
  - `predicted_occupancy`, `current_price`, `available_spots`
  - `available_handicap`, `available_ev`, `available_regular`
  - `recent_occupancy[]` (24 data points)

**Frontend rendering** (`SlotPicker` component in FindPage.tsx):
- Back button + lot name/address
- Meta bar: available spots count, $/hr, predicted occupancy %
- Slot type counts: regular, handicap (if>0), EV (if>0)
- Slot grid: min(max(available, 8), 20) buttons, 4 columns
  - Selected slot gets cyan gradient + glow
  - Clicking a slot selects it
- "Park in Slot N" CTA button → calls `startSession(lot_id, slot)` → WF#14

### WF#13 Reserve Modal (Prebook Flow)
**Frontend**: `ReserveModal` in FindPage.tsx
- Opens when "Reserve" button clicked on lot card
- Loads lot detail to get available_spots
- Form fields:
  - Slot selection dropdown (1..min(max(available_spots, 8), 16))
  - Arrival time (datetime-local, 5min to 6hr window)
- Cost breakdown: Booking Fee ($2) + Refundable Deposit ($base_price * 1.0)
- "Confirm Reserve" → calls `prebookSlot(lot_id, slot, targetTime)` → WF#17
- Success → `ReserveSuccessModal` with slot #, rate, probability, grace period
  - "Go to My Bookings" → navigates to /driver/bookings

---

## PHASE 4: SESSIONS (WF#14-WF#16)

### WF#14 Start Session
**Frontend**: `driverClient.startSession(lotId, slot)` → `POST /sessions/start`

**Backend**: `sessions.py:19-36` → `POST /api/v1/sessions/start`
- Delegates to `session_service.create_session()`

**Service**: `session_service.py:18-87` `create_session()`
1. **Stale session cleanup**: Cancel any running sessions older than `SESSION_STALE_HOURS`
2. **Duplicate check**: If driver already has active session:
   - `force=False` (default) → raise RuntimeError("driver already has an active session")
   - `force=True` → cancel existing session, continue
3. **Lot validation**: Query ParkingLot → RuntimeError if not found
4. **Build features**: Get recent records + `build_features_from_records()` if enough records
5. **pipeline.start_session()**:
   - Create IoT sensor simulator for lot
   - `sample_step()` → ultrasonic + vision readings
   - `DualSensorPair.clean_reading()` → fused occupancy
   - ML prediction of occupancy
   - RL pricing → new_price + multiplier
   - Actuate: close barrier, set pricing board, congestion light
   - Smart contract: allocation_contract.execute() for spot allocation
   - IPFS pin session data
   - Ledger add_transaction (type: session_start)
6. **Create DB records**:
   - `ParkingSession` record (session_id, lot_id, driver_id, slot, entry_price, status=SESSION_RUNNING)
   - `PredictionMetric` record (predicted_occupancy, model_version)
   - Outbox: enqueue ledger transaction
7. Commit + process pending ledger outbox

**Response**: `SessionStartResponse` with session_id, price_at_entry, predicted_occupancy, iot_consensus, weather_factor, blockchain_ref, digital_twin, layers_activated

**Frontend rendering**: On success → `window.location.hash = '/driver/active'`
On failure → error banner "Failed to start session. Please try again."

### WF#15 End Session
**Frontend**: `ActiveSessionPage.tsx` → `driverClient.endSession(sessionId)` → `POST /sessions/end`

**Backend**: `sessions.py:39-115`
1. Query ParkingSession (session_id + status=SESSION_RUNNING)
   - Not found → 404
   - Wrong driver → 403
2. Get latest OccupancyRecord for current_occ
3. `pipeline.end_session()`:
   - Calculate duration_hours from start_time
   - Compute current_rate via RL pricing (informational)
   - `amount = entry_price * duration_hours` capped at `price_cap * 24`
   - IPFS pin + ledger transaction (type: session_fee)
   - `_slot_op(slot, available)` → release slot in state engine
   - Actuate: update pricing board, barrier, congestion light
   - **Digital Twin**: add/update zone with real occupancy+price, call tick()
   - **CVAE-WGAN online_update**: fine-tune on real outcome every 10 sessions
4. Update session: status=SESSION_PENDING_SETTLEMENT, end_time, duration_minutes, final_price, amount_charged
5. **Grace period**: if duration ≤ FREE_GRACE_MINUTES → amount_charged = 0
6. **Settlement**: `settle_session()`:
   - Find active prebook for this driver/lot/slot
   - If deposit exists and not refunded:
     - If amount_charged > deposit → overcharge = difference, deduct from balance
     - If deposit > amount_charged → refund difference to balance
   - Mark deposit_refunded
   - Enqueue ledger outbox for session fee
7. Update PredictionMetric with actual_occupancy + MAE
8. Commit + process ledger outbox
9. Return `SessionEndResponse` with all billing details, deposit_refund

**Frontend rendering** (`ActiveSessionPage.tsx`):
- Loading → "Checking active session..."
- No session → "No Active Session" → "Find Parking" CTA
- Active session view:
  - Animated pulse circle + timer (start_time countdown)
  - Slot # and $/hr display
  - "End Parking" button (rose)
  - Status `pending_settlement` → shows payment due card instead
- Ended view (post-endSession):
  - "Session Ended" with amount due
  - "Pay" button → triggers WF#16
  - Deposit refund notice (green, if applicable)
- Receipt view (post-confirmPayment):
  - "Parking Complete" with duration, rate, charged amount
  - Blockchain tx reference
  - "View History" CTA

### WF#16 Confirm Payment
**Frontend**: `ActiveSessionPage.tsx` → `driverClient.confirmPayment(sessionId)` → `POST /payments/confirm`

**Backend**: `payments.py:15-111` → `POST /api/v1/payments/confirm`
- Auth required
- Query ParkingSession by session_id
  - Not found → 404
  - Wrong driver → 403
  - Already SETTLED → return already_paid=True (idempotent)
  - Not PENDING_SETTLEMENT → 400 "must be ended first"
- **Idempotency key**: if provided and existing Transaction found → return already_paid
- `pipeline.process_payment()`:
  - Generate tx_hash
  - IPFS pin payment confirmation
  - Ledger: add payment_confirmation transaction
  - **Revenue share contract**: execute with price/driver/lot
    - Distributions: city (70%), lot_owner (30%)
    - System fee: 15%
  - Ledger: add revenue_share transaction
- Create Transaction record, update session (payment_tx, payment_blockchain_ref, status=SETTLED)
- Update/Create RevenueRecord for today (increment transactions, revenue, avg_price)
- Enqueue outbox + commit + process_pending
- Return `PaymentConfirmResponse(tx_hash, amount, blockchain_ref, ledger_blocks)`

**Frontend rendering**: receipt view (see WF#15)

---

## PHASE 5: PREBOOKING & WALLET (WF#17-WF#22)

### WF#17 Prebook Slot
**Frontend**: `ReserveModal` → `driverClient.prebookSlot(lotId, slot, targetTime)` → `POST /micro/prebook`

**Backend**: `micro/prebooks.py:27-154`
- Auth required; rate limiter (5/min per driver)
1. Validate target_time (ISO 8601, must be ≤ MAX_PREBOOK_HOURS from now)
2. Query ParkingLot → 404 if not found
3. Query all active MicroSlots for lot
4. `slot_pricing.compute_modifiers()` + `_rank_slots()` → rank available slots
5. **Balance check**: Query User.balance; must have ≥ BOOKING_FEE + deposit_amount (base_price * DEPOSIT_RATE)
   - Insufficient → 400 "Insufficient balance"
6. Try each ranked slot in order:
   - If state is AVAILABLE → `slot_state_engine.prebook(slot_id, did, target_epoch)`
   - If success → assigned
7. No slot available → 409 "None of the requested slots available"
8. Deduct balance: booking_fee ($2) + deposit ($base_price * DEPOSIT_RATE)
9. Create Transactions (fee + deposit), PrebookRecord (status=RESERVATION_ACTIVE)
10. Return `PrebookResponse(prebook_id, assigned_slot_index, slot_label, probability, price_at_booking, expires_at)`

**Frontend rendering**: `ReserveSuccessModal` with slot, rate, probability, grace period

### WF#18 Confirm Prebook (Arrive)
**Frontend**: `BookingsPage` → `driverClient.confirmPrebook(prebookId)` → `POST /micro/confirm`

**Backend**: `micro/prebooks.py:157-276`
1. Query PrebookRecord (prebook_id + driver_id) → 404
2. Status must be RESERVATION_ACTIVE → 400 if not
3. **Expired** → set NO_SHOW, cleanup_expired → 410 "deposit forfeited"
4. Check slot state engine:
   - If slot is PREBOOKED or RESERVED → `_mk_session()` (creates session via session_service) + `confirm_prebook()` → start ParkingSession, return session_id
   - If slot is available → try `prebook()` then `_mk_session()`
   - If slot is unavailable → `_find_fallback_slot()` → try alternate slot
   - If no fallback → refund deposit to driver's balance → set status=REFUNDED → return 409

**Frontend rendering**:
- Success → redirect to `/driver/active` (session started)
- Failure → error banner with reason; reload bookings

### WF#19 Cancel Prebook
**Frontend**: `BookingsPage` → `driverClient.cancelPrebook(prebookId)` → `POST /micro/cancel`

**Backend**: `micro/prebooks.py:320-371`
1. Query PrebookRecord → 404
2. Status must be ACTIVE → 400
3. `slot_state_engine.release_prebook()` → release slot in state engine
4. **Deposit refund**: refund_amount = deposit * (1 - ADMIN_FEE_RATE)
   - Credit to driver balance
   - Create Transaction refund record
   - Mark deposit_refunded
5. Set status = CANCELLED

**Frontend rendering**: Reload bookings list → sees updated status

### WF#20 List Prebooks
**Frontend**: `BookingsPage` → `driverClient.fetchPrebooks()` → `GET /micro/prebooks/list`

**Backend**: `micro/prebooks.py:279-317`
- Query all PrebookRecords for driver_id (ordered desc)
- Join MicroSlot → slot_label
- Join ParkingLot → lot_name
- Return rich list with all financial fields

**Frontend rendering** (`BookingsPage.tsx`):
- Loading → "Loading bookings..."
- Empty → "No bookings scheduled"
- Each booking card:
  - Header: status dot, lot_name, prebook_id, status badge (color-coded)
  - Details: arrival time, slot #, rate, total deducted
  - Active bookings: countdown timer + Cancel/Arrive buttons
  - Cancelled bookings: "Deposit Refunded" notice (green, 90%)

### WF#21 Wallet Balance & Top-Up
**Frontend**: `DashboardPage.tsx` → `driverApi.get('/wallet')` + `topupWallet(amount)` → `POST /wallet/topup`

**Backend**: `wallet.py:32-60`
- `GET /api/v1/wallet`: Query User by id → return balance
  - User not found → 404
- `POST /api/v1/wallet/topup`:
  - Validate amount (gt 0, le 100000)
  - Query User → 404
  - Update balance += amount
  - Create Transaction (action="deposit", driver_id=email)
  - Return new balance + amount_added

**Frontend rendering**: Wallet card with Fraunces balance display, Top Up button → modal with presets ($5/$10/$20/$50) + custom input

### WF#22 Wallet Transactions
**Frontend**: `TransactionsPage.tsx` → `fetchWalletTransactions()` → `GET /wallet/transactions`

**Backend**: `wallet.py:63-80`
- Query Transaction by driver_id (email), order desc
- Return all: tx_hash, action, amount, status, lot_id, timestamp, session_id

**Frontend rendering** (`TransactionsPage.tsx`):
- Loading → animation
- Empty → "No transactions yet"
- Each tx card:
  - ActionBadge (deposit→green, booking_fee→red, refund→amber, session_fee→blue)
  - StatusBadge
  - TX hash (truncated), lot_id, session_id
  - Amount colored: additions (deposit/refund) = green with '+' prefix, others = white with '-' prefix

---

## PHASE 6: ADMIN DASHBOARD (WF#23-WF#27)

### WF#23 Admin Dashboard
**Frontend**: `admin/DashboardPage.tsx` → `fetchDashboard()` → `GET /admin/dashboard`

**Backend**: `admin.py:58-167`
1. `require_admin(user)` → 403 if not admin
2. Query all ParkingLots
   - **Auto-seed**: if 0 lots → `seed_all(session, days=7)` → populate with 5 demo lots + 7 days of data
3. Aggregate stats: total_lots, total_slots, total_users, total_revenue (RevenueRecord), total_tx (Transaction)
4. Latest occupancy per lot (subquery with MAX timestamp)
5. Occupancy trend: hourly average over 24h (via db_extract_hour())
   - Fallback: static [hour: rate=0] for hours 6-22 step 2
6. Revenue 7d: daily sum over 7 days (via db_date())
   - Fallback: zeros for last 7 days
7. Alerts: OccupancyRecords > 0.9 in last 1h → severity=warning if >0.95 else info
8. System health via `_build_system_health()`:
   - IoT: "operational" if recent_occ > 0, "simulated" if has_data but no recent, "no_data" if no lots
   - ML: "operational" if artifacts dir exists
   - Blockchain: "operational" if ledger.validate_chain()
   - RL: "operational" if pipeline.pricing.agent_available
   - DigitalTwin: "operational" if dt.zones non-empty
   - API: always "operational"

**Frontend rendering**: DashboardPage with narrative feed, stats cards, occupancy trend chart, revenue chart, lot summaries, alerts list

### WF#24 Admin Analytics
**Frontend**: `admin/AnalyticsPage.tsx` → `fetchAnalytics()` → `GET /admin/analytics`

**Backend**: `admin.py:170-221`
1. Hourly occupancy: avg by hour over 24h
2. Lot comparison: per-lot revenue (30d), latest occ, computed efficiency = min(100, occ*0.7 + 30)
3. System perf metrics: avg_occupancy, API latency (45ms), data freshness (30s), blockchain height

### WF#25 Admin Alerts
**Frontend**: `admin/AlertsPage.tsx` → `fetchAlerts()` → `GET /admin/alerts`

**Backend**: `admin.py:226-243`
- Query OccupancyRecords > 0.9 in last hour, limit 20
- If real alerts exist → return formatted AlertItems
- If empty → return []
- Resolve: `PUT /admin/alerts/{id}/resolve` → removes from in-memory store

### WF#26 Admin System Health
**Frontend**: `adminClient.fetchHealth()` → `GET /admin/system-health`

**Backend**: `admin.py:254-257` → same `_build_system_health()` as dashboard

### WF#27 Admin Seed Data
**Frontend**: Via admin panel → `POST /admin/seed`

**Backend**: `admin.py:260-265`
- Wipe all data + re-seed with 7 days of realistic data via `seed_all()`

---

## PHASE 7: MICRO SLOTS (WF#28-WF#32)

### WF#28 List MicroSlots
**Frontend**: `adminClient.fetchMicroSlots(lotId)` → `GET /micro/lots/{lot_id}/slots`

**Backend**: `micro/slots.py:17-56`
- Validate ParkingLot exists → 404
- Query all active MicroSlots for lot
- `slot_state_engine.occupancies(lot_id, all_slots)` → state counts
- Paginate
- Compute modifiers via `slot_pricing.compute_modifiers(page)`
- Return `SlotsListResponse` with counts + per-slot data (state, probability, price)

### WF#29 Slot Probability
**Backend**: `micro/slots.py:59-92`
- Query MicroSlot by lot_id + slot_index → 404
- `slot_predictor.predict(slot_id, target_time)` → Beta-Binomial probability
- `slot_state_engine.get_state(slot_id)` → current state
- `slot_pricing.slot_price()` → adjusted price with modifier
- Return probability, state, price

### WF#30 Reserve Slot (Legacy)
**Backend**: `micro/reservations.py:25-86`
- Find MicroSlot → 404
- `slot_state_engine.reserve(slot_id, did)` → false=409
- Predict probability
- Create SlotReservation record
- Return reservation_id, probability, expires_at

### WF#31 Release Slot (Legacy)
**Backend**: `micro/reservations.py:89-125`
- Rate limited (10/min)
- Find SlotReservation → 404
- `slot_state_engine.release(slot_id, did)` → false=400
- Mark released

### WF#32 Micro Slot Admin
**Backend**: `micro/admin.py` — slot/capacity management, seeding

---

## PHASE 8: BLOCKCHAIN & PRICING & ML (WF#33-WF#37)

### WF#33 Get Blockchain Status
**Backend**: `src/api/routes/blockchain.py`
- `GET /api/v1/blockchain/status` → ledger chain info
- `GET /api/v1/blockchain/chain` → full chain
- `GET /api/v1/blockchain/pending` → pending transactions
- `POST /api/v1/blockchain/mine` → mine block, save to file
- `POST /api/v1/blockchain/transaction` → add pending transaction

### WF#34 Pipeline Status
**Frontend**: `driverClient` → `GET /driver/pipeline/status`

**Backend**: `driver.py:116-118` → `pipeline.status()`
- ML models summary
- RL agent available
- Blockchain chain_length + pending_tx
- DigitalTwin zones summary
- Actuator summary

### WF#35 Model Prediction (Independent)
**Backend**: `prediction.py:78-109` → `POST /api/v1/predict/occupancy`
- Auth required
- Load models → 503 if not trained
- Build 19-feature row from input
- RF + XGB + meta ensemble → clipped [0,1]

### WF#36 Model Health
**Backend**: `prediction.py:112-119` → `GET /api/v1/predict/health`
- Check if models loaded → healthy/unhealthy

### WF#37 Pricing Routes
**Backend**: `pricing.py` → `GET /api/v1/pricing/lots`
- Per-lot pricing data from RL agent + digital twin

---

## PHASE 9: IoT & DIGITAL TWIN & ACTUATOR (WF#38-WF#43)

### WF#38 IoT Ingestion
**Backend**: `ingestion.py`
- `POST /ingestion/sensor-readings` → DualSensorPair fusion
- `POST /ingestion/occupancy` → raw occupancy write (fusion bypass warning)
- Role check: admin, lot_owner, sensor

### WF#39 Digital Twin Scenarios
**Backend**: `digital_twin.py`
- `POST /scenarios/run` → `pipeline.run_digital_twin_scenario()`
  - `dt.get_zone_state(zone_id)` → if not found, `bootstrap_from_db()`
  - `scenario_engine.run_all(base_state)` → 5 counterfactuals
  - CVAE generates per-scenario conditioned state
- Returns all scenarios + comparisons

### WF#40 Digital Twin Status
**Backend**: `digital_twin.py` status endpoint
- Zone count, summary, STID predictions

### WF#41 Actuator Status
**Backend**: `actuator.py` endpoints
- `GET /actuators/status` → actuator bridge summary
- Per-actuator state (barriers, pricing boards, congestion lights)

### WF#42 Simulation Ingest
**Backend**: `simulation.py`
- Periodic simulation of occupancy data for all lots
- Calls `pipeline.simulate_ingest()` → drift-based occupancy + RL pricing

### WF#43 MARL Routes
**Backend**: `marl.py`
- Multi-agent RL status and configuration

---

## PHASE 10: LANDING PAGE COMPONENTS (WF#44-WF#52)

All landing page components are pure client-side with hardcoded data (`D` object). No API calls.

### WF#44 Rush Hour Timeline
**Section #rush** in `landing/index.html`
- Pure static data (pre-computed 15-step rush hour scenario)
- Auto-advances every 1200ms
- User click pauses for 5s
- Shows: price, occupancy bar, predicted bar, arrival rate, ML confidence, overflow warning
- Scroll reveal animation

### WF#45 Advance Booking Radial
**Section #booking** in `landing/index.html`
- Canvas-drawn concentric radial arcs
- 7-step booking timeline (T-7h to T-1h)
- Colors: Off-peak (sage), Standard (gold), Rising (rose)
- 30-slot grid with fill animation
- Price display at center of radial

### WF#46 MARL City Grid
**Section #marl** in `landing/index.html`
- Canvas-drawn 4-zone city grid
- 15-step overflow + reroute scenario
- Zone bars with color-coded occupancy
- Overflow alert + reroute badge

### WF#47 Cancellation Cascade
**Section #cancel** in `landing/index.html`
- Canvas line chart (peak + net occupancy, cancellation bars)
- 9-step price spike scenario ($14→$20→$11 recovery)
- 18% cancellation spike at step 3
- Peak/Cancel/Net bars sidebar

### WF#48 Blockchain Chain
**Section #chain** in `landing/index.html`
- Horizontal scrollable block chain
- 10 blocks with hash, nonce, event, amount
- Auto-advances every 2200ms
- Genesis block special styling
- Arrow connectors between blocks

### WF#49 Hero Section
- Animated entrance (staggered reveal)
- 5 tech tags
- "Launch App" CTA → https://pragma-4szs.onrender.com

### WF#50 Custom Cursor
- Gold dot + ring with difference blend mode
- Ring expands on hover over interactive elements
- Smooth interpolation animation

### WF#51 Scroll Reveal
- IntersectionObserver on all .reveal elements
- Threshold 0.1, rootMargin -40px
- One-shot: unobserve after first reveal

### WF#52 Navigation
- Fixed top bar (blur backdrop)
- Section anchors (#rush, #booking, #marl, #cancel, #chain)
- SYSTEM LIVE dot with pulse animation
- "LAUNCH APP" pill → production URL

---

## COMPLETE API ROUTE MAP

| Method | Path | Auth | File | WF# |
|--------|------|------|------|-----|
| GET | /health | No | server.py | WF#0 |
| POST | /auth/login | No | auth.py:69 | WF#1/#2 |
| GET | /auth/me | Yes | auth.py:89 | WF#3 |
| POST | /auth/logout | Yes | auth.py:108 | WF#4 |
| POST | /auth/register | No | auth.py | — |
| GET | /lots | No | lots.py:15 | WF#5 |
| GET | /lots/owner | Yes | lots.py:61 | — |
| POST | /lots | Admin | lots.py:30 | WF#9 |
| PUT | /lots/{id}/config | Owner/Admin | lots.py:83 | WF#10 |
| GET | /lots/{id} | Yes | lots.py:129 | WF#6 |
| GET | /lots/{id}/occupancy | No | lots.py:158 | WF#7 |
| GET | /lots/{id}/predictions | Yes | lots.py:191 | WF#8 |
| GET | /driver/lots | Yes | driver.py:39 | WF#11 |
| GET | /driver/lots/{id} | Yes | driver.py:67 | WF#12 |
| GET | /driver/pipeline/status | Yes | driver.py:116 | WF#34 |
| POST | /sessions/start | Yes | sessions.py:19 | WF#14 |
| POST | /sessions/end | Yes | sessions.py:39 | WF#15 |
| GET | /sessions/active | Yes | sessions.py:170 | — |
| GET | /sessions/active/{lot_id} | Yes | sessions.py:118 | — |
| GET | /sessions/history | Yes | sessions.py:140 | — |
| GET | /sessions/{id} | Yes | sessions.py:197 | — |
| GET | /sessions/{id}/pricing | Yes | sessions.py:221 | — |
| GET | /sessions/{id}/receipt | Yes | sessions.py:252 | — |
| POST | /payments/confirm | Yes | payments.py:15 | WF#16 |
| GET | /payments/history | Yes | payments.py:113 | — |
| GET | /wallet | Yes | wallet.py:32 | WF#21 |
| POST | /wallet/topup | Yes | wallet.py:41 | WF#21 |
| GET | /wallet/transactions | Yes | wallet.py:63 | WF#22 |
| GET | /admin/dashboard | Admin | admin.py:58 | WF#23 |
| GET | /admin/analytics | Admin | admin.py:170 | WF#24 |
| GET | /admin/alerts | Admin | admin.py:226 | WF#25 |
| PUT | /admin/alerts/{id}/resolve | Admin | admin.py:246 | — |
| GET | /admin/system-health | Admin | admin.py:254 | WF#26 |
| POST | /admin/seed | Admin | admin.py:260 | WF#27 |
| GET | /micro/lots/{id}/slots | Yes | micro/slots.py:17 | WF#28 |
| GET | /micro/lots/{id}/slots/{idx}/probability | Yes | micro/slots.py:59 | WF#29 |
| POST | /micro/reserve | Yes | micro/reservations.py:25 | WF#30 |
| POST | /micro/release | Yes | micro/reservations.py:89 | WF#31 |
| POST | /micro/prebook | Yes | micro/prebooks.py:27 | WF#17 |
| POST | /micro/confirm | Yes | micro/prebooks.py:157 | WF#18 |
| POST | /micro/cancel | Yes | micro/prebooks.py:320 | WF#19 |
| GET | /micro/prebooks/list | Yes | micro/prebooks.py:279 | WF#20 |
| POST | /predict/occupancy | Yes | prediction.py:78 | WF#35 |
| GET | /predict/health | Yes | prediction.py:112 | WF#36 |
| GET | /pricing/lots | Yes | pricing.py | WF#37 |
| GET | /blockchain/status | Yes | blockchain.py | WF#33 |
| GET | /blockchain/chain | Yes | blockchain.py | — |
| GET | /blockchain/pending | Yes | blockchain.py | — |
| POST | /blockchain/mine | Yes | blockchain.py | — |
| POST | /blockchain/transaction | Yes | blockchain.py | — |
| POST | /ingestion/sensor-readings | Sensor | ingestion.py | WF#38 |
| POST | /ingestion/occupancy | Admin | ingestion.py | — |
| POST | /scenarios/run | Yes | digital_twin.py | WF#39 |
| GET | /scenarios/status | Yes | digital_twin.py | WF#40 |
| GET | /actuators/status | Yes | actuator.py | WF#41 |
| POST | /simulate/ingest | Admin | simulation.py | WF#42 |
| GET | /revenue/overview | Admin | revenue.py | — |

---

## CRITICAL STATE ENGINES & SINGLETONS

### Slot State Engine (`slot_state_engine`)
- In-memory dict: `{slot_id: {state, driver, expires_at, prebook_data}}`
- States: `AVAILABLE`, `OCCUPIED`, `RESERVED`, `PREBOOKED`
- Operations: `prebook()`, `confirm_prebook()`, `release_prebook()`, `reserve()`, `release()`, `set_state()`, `get_state()`, `occupancies()`, `cleanup_expired()`
- **State transition logging**: `_on_transition()` fires on all state changes → updates SlotStateLog for Beta-Binomial predictor

### BlockchainLedger
- File-backed (JSON, default `data/blockchain.json`)
- SHA-256 PoW mining
- IPFS off-chain store with JSON persistence
- Validation: `validate_chain()` checks hash chain integrity

### DigitalTwinSimulator
- In-memory zone dict: `{zone_id: {occupancy, price, capacity, ...}}`
- 100-zone STID predictor (spatial-temporal embeddings)
- Bootstrap from DB when zone not found

### PipelineOrchestrator
- Global singleton with `threading.Lock()` for all critical operations
- Lazy MARL init from DT zones
- 6-layer pipeline: IoT→ML→Blockchain→RL→Digital Twin→Actuator
