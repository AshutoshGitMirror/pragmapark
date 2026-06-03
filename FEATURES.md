# Pragmapark — Complete Feature Catalog

## 1. FRONTENDS (4 surfaces)

### 1A. Admin Dashboard SPA — `GET /` → `src/dashboard/templates/index.html`
| View | Features | API Endpoints Called |
|------|----------|---------------------|
| Login | Email/password form, JWT stored, role check, "Create Account" | POST `/api/v1/auth/login`, POST `/api/v1/auth/register` |
| Dashboard | Stats grid (lots, users, revenue, txns, occupancy), Occupancy bar chart, Revenue 7-day line chart, Lot table with city filter | GET `/api/v1/admin/dashboard`, GET `/api/v1/lots?city=X` |
| Parking Lots | Stats per lot, detail table with all lots | GET `/api/v1/lots` |
| Analytics | Hourly occupancy pattern (line), Lot comparison (radar), System performance (doughnut) | GET `/api/v1/lots/{id}`, GET `/api/v1/lots/{id}/occupancy` |
| Revenue | Stats grid, revenue per lot table | GET `/api/v1/revenue/overview?days=30` |
| Map | Leaflet map with city-filter, colored markers per city | GET `/api/v1/lots` |
| Micro Slots | Lot selector, slot grid heatmap (colored by state), slot detail dialog (state, prob, type, price, modifier, adj price) | GET `/api/v1/micro/lots/{id}/slots` |
| Alerts | Alert list with count badge | GET `/api/v1/admin/system-health` |
| My Lots | Lots owned by current user (owner view) | GET `/api/v1/lots/owner` |
| Settings | Profile editor (name, org), dark theme toggle | PUT `/api/v1/lots/{id}/config` |
| Navigation | Sidebar with 8 views, mobile hamburger menu, keyboard trap, Escape to close | — |
| Speed controls | Admin simulation speed: 1x/10x/60x | POST `/api/v1/simulation/speed` |
| Accessibility | Skip-to-content link, aria-live regions, focus management, aria-label on interactive elements | — |

### 1B. Driver Mobile App — `GET /app/driver` → `src/dashboard/templates/driver.html`
| Screen | Features | API Endpoints Called |
|--------|----------|---------------------|
| **Find** | Search lots by name/city/address, lot cards with occupancy bar (color-coded), price tag, base price, avail spots badge, skeleton loading | GET `/api/v1/driver/lots?offset=&limit=&slot_type=&max_price=` |
| **Lot Detail** | Back nav, total spots/base/predicted%, mini occupancy bars (24h), **slot grid** (color-coded cells: Free/Reserved/Prebooked/Occupied/Maintenance), filter chips by slot type, selected slot bar (label, state, price, prob), Reserve/Book Later/Release buttons | GET `/api/v1/driver/lots/{id}`, GET `/api/v1/micro/lots/{id}/slots` |
| **Reserve** | Reserve a slot with TTL countdown (auto-expires), release reservation, toast feedback | POST `/api/v1/micro/reserve`, POST `/api/v1/micro/release` |
| **Pre-book** | Pre-book form: select up to 3 slots, target time (1h/2h/4h/8h/custom), confirm/cancel, deposit deducted | POST `/api/v1/micro/prebook` |
| **Active Session** | Session card with timer (MM:SS), running cost, lot name, rate/hr, slot#, end session + pay button | — (started via sessions/start) |
| **Start Session** | Creates parking session, displays active screen, slot info (label/type badge) | POST `/api/v1/sessions/start` |
| **End Session** | Ends session, retries payment up to 3x with idempotency key, fallback retry button | POST `/api/v1/sessions/end`, POST `/api/v1/payments/confirm` |
| **Receipt** | Paid! screen with lot, slot, duration, entry/final rate, total charged, on-chain ref | — |
| **History** | Paginated session history with status badges (settled/running/pending/cancelled) | GET `/api/v1/sessions/history?offset=&limit=` |
| **Bookings** | Active pre-books list, confirm ("I'm Here Now"), cancel, expiry countdown | GET `/api/v1/micro/prebooks/list`, POST `/api/v1/micro/confirm`, POST `/api/v1/micro/cancel` |
| **Login/Register** | Email/password sign in, create account with name, validation, error display, welcome toast | POST `/api/v1/auth/login`, POST `/api/v1/auth/register` |
| **Wallet** | Balance badge in header, auto-loaded on auth | GET `/api/v1/wallet` |
| **Bottom Nav** | 4 tabs: Find, Session, Bookings, History — with aria-current, keyboard nav | — |
| **Speed Controls** | Appears when simulation active, 1x/10x/60x | POST `/api/v1/simulation/speed`, GET `/api/v1/simulation/status` |
| **Escape Handling** | Escape key goes back one screen, screen stack | — |
| **Prebook from Grid** | Tap available slots in grid to add to prebook choices (max 3), remove choices | — |

### 1C. Plotly Dash Dashboard — `python -m src.dashboard.app` → port 8050
| Layer | Feature | Update Interval |
|-------|---------|----------------|
| IoT | Occupancy Rate + Net Flux time series | 5s |
| ML | Actual target vs SMA-5 forecast line chart | 5s |
| Blockchain | Per-lot bar chart (blocks colored by occupancy) + pending TX count | 5s |
| RL | Occupancy vs Dynamic Price dual-axis, agent status annotation | 5s |
| Digital Twin | Scenario impact bar chart (6 scenarios) | 5s |
| MARL | Multi-zone occupancy bars + price overlay dual-axis | 5s |
| Micro Slots | Per-slot heatmap with lot selector, row/position axes, hover tooltip with status | 15s |

### 1D. React Demo SPA — `demo/app/` (standalone)
| Section | Features | API Endpoints |
|---------|----------|---------------|
| Hero | Three.js particle globe, MetricTicker (live badges), CTA link | GET `/api/v1/lots`, GET `/api/v1/admin/dashboard` |
| Prediction | Lot selector, time range (6/12/24h), Recharts line chart predicted vs actual | GET `/api/v1/lots/{id}/occupancy?hours=N` |
| Revenue Intelligence | RL heatmap (7d×24h), clickable cells with tooltip, color legend | GET `/api/v1/pricing/zones` |
| Blockchain Ledger | Block chain viz (5 blocks), Mine Block (simulated), +New Transaction form | GET `/api/v1/blockchain/status` |
| Digital Twin | 6 scenario cards with Run Simulation, results display | GET `/api/v1/digital-twin/scenarios`, POST `/api/v1/digital-twin/scenarios/run` |
| Micro Slot Grid | 200 clickable slot grid, per-slot tooltip, stats/legend | GET `/api/v1/micro/lots/A1/slots` |
| Architecture Diagram | 6-layer visual with component cards, connection legend | — |
| Live Terminal | Simulated system logs, filter (All/Info/Warn/Error), Pause/Resume, Clear | — |
| Testimonials | Auto-rotating (6s) testimonial carousel, dot navigation | — |
| Footer | Brand, vision, tech stack pills, placeholder links | — |
| WarmupOverlay | Full-screen overlay while backend cold-starts, polls health, "Continue with Simulation" skip button | GET `/api/v1/health` |
| All sections | `useApiWithFallback` pattern: instant render with hardcoded data, background fetch, seamless live swap | polling via WarmupContext |

---

## 2. BACKEND API (60 endpoints, 15 DB tables)

### 2A. Auth & Users
| Endpoint | Auth | Request | Response |
|----------|------|---------|----------|
| POST `/api/v1/auth/register` | — | `{email, password, full_name?, organization?, role?}` | `{access_token, user}` |
| POST `/api/v1/auth/login` | — | `{email, password}` | `{access_token, user}` |
| POST `/api/v1/auth/logout` | Bearer | — | `{message}` |
| GET `/api/v1/auth/me` | Bearer | — | `{id, email, full_name, role, organization}` |

### 2B. Parking Lots
| Endpoint | Auth | Params | Response |
|----------|------|--------|----------|
| GET `/api/v1/lots` | Bearer | `city?, offset?, limit?` | `[LotSummary]` (21 lots, 10 cities) |
| POST `/api/v1/lots` | Bearer+admin | `{lot_id, name, total_slots, base_price, address?, city?, price_cap?}` | `{status, lot_id}` |
| GET `/api/v1/lots/{id}` | Bearer | — | `{LotDetail + history[100]}` |
| GET `/api/v1/lots/{id}/occupancy` | Bearer | `hours?(1-168), offset?, limit?` | `{records}` |
| PUT `/api/v1/lots/{id}/config` | Bearer+owner | `{name?, total_slots?, base_price?, price_cap?}` | `{status, lot_id, base_price, price_cap}` |
| GET `/api/v1/lots/owner` | Bearer | `offset?, limit?` | `[LotSummary]` |

### 2C. Driver
| Endpoint | Auth | Params | Response |
|----------|------|--------|----------|
| GET `/api/v1/driver/lots` | Bearer | `offset?, limit?, slot_type?, max_price?` | `{lots: [DriverLotSearchItem]}` with predicted_occupancy, available_spots, dynamic_price, handicap/ev/regular counts |
| GET `/api/v1/driver/lots/{id}` | Bearer | — | `DriverLotDetail` with recent_occupancy, predicted_occupancy, slot counts |
| GET `/api/v1/driver/pipeline/status` | Bearer | — | `{ml_models, rl_agent, blockchain, digital_twin, actuator}` |

### 2D. Predictions (ML Layer)
| Endpoint | Auth | Request | Response |
|----------|------|---------|----------|
| POST `/api/v1/predict/occupancy` | Bearer | `{occupied_slots, total_slots, occ_lag_15m, occ_lag_1h, net_flux, hour?}` | `{rf_prediction, xgb_prediction, ensemble_prediction, mae?}` |
| GET `/api/v1/predict/health` | Bearer | — | `{rf_loaded, xgb_loaded, status}` |

### 2E. Pricing (RL Layer)
| Endpoint | Auth | Request | Response |
|----------|------|---------|----------|
| POST `/api/v1/pricing/adjust` | Bearer | `{predicted_occupancy, current_price}` | `{price_multiplier, new_price, is_hike}` |
| GET `/api/v1/pricing/zones` | Bearer | `zone_id?(default: BHMBCCMKT01)` | `{zone_id, base_price, price_range, currency, dynamic_pricing}` |

### 2F. Blockchain
| Endpoint | Auth | Request | Response |
|----------|------|---------|----------|
| GET `/api/v1/blockchain/status` | Bearer+admin | — | `{chain_length, chain_valid, last_block_hash, pending_transactions}` |
| POST `/api/v1/blockchain/transaction` | Bearer+rate-limited | `{driver_id, lot_id, action, price?, duration_minutes?}` | `{tx_hash, block_index, status}` |
| POST `/api/v1/blockchain/mine` | Bearer+admin | — | `{block_index, hash, transactions, nonce, timestamp}` |
| GET `/api/v1/blockchain/pool/{pool_id}` | Bearer+admin | — | `PoolDetail` |
| POST `/api/v1/blockchain/pool/create` | Bearer+admin | `{pool_id, total_spots, owner?}` | `{status, pool_id, total_spots}` |

### 2G. Digital Twin
| Endpoint | Auth | Request | Response |
|----------|------|---------|----------|
| GET `/api/v1/digital-twin/scenarios` | Bearer | `offset?, limit?` | `[ScenarioListItem]` |
| POST `/api/v1/digital-twin/scenarios/run` | Bearer | `ScenarioRequest` | `{base_state, results, comparisons}` |
| POST `/api/v1/digital-twin/generate` | Bearer+admin | `{base_occupancy?, base_price?}` | `{synthetic_occupancy, synthetic_price, congestion_score}` |
| POST `/api/v1/digital-twin/scenario` | Bearer | `{scenario_type?, zone_id?}` | `{scenario, zone_id, result, all_scenarios, comparisons}` |
| POST `/api/v1/digital-twin/train-generator` | Bearer+admin | `{epochs?}` | `{status, epochs, final_loss}` |

### 2H. MARL (Multi-Agent RL)
| Endpoint | Auth | Request | Response |
|----------|------|---------|----------|
| POST `/api/v1/marl/train` | Bearer+admin | `{num_zones?, episodes?}` | `{status, num_zones, episodes, final_reward, validation}` |
| GET `/api/v1/marl/status` | Bearer | — | `{status, num_zones?, episodes_completed?, mean_reward?, validation?}` |

### 2I. Sessions
| Endpoint | Auth | Request | Response |
|----------|------|---------|----------|
| POST `/api/v1/sessions/start` | Bearer | `{lot_id, slot?, force?, flat_rate?, payment_method?}` | `SessionStartResponse` (16 fields incl. all 6 layers) |
| POST `/api/v1/sessions/end` | Bearer | `{session_id}` | `SessionEndResponse` (13 fields incl. deposit_refund) |
| GET `/api/v1/sessions/active/{lot_id}` | Bearer | `offset?, limit?` | `{lot_id, active_count, sessions}` |
| GET `/api/v1/sessions/history` | Bearer | `offset?, limit?` | `{total_sessions, sessions}` |
| GET `/api/v1/sessions/{session_id}` | Bearer | — | `SessionDetail` |
| GET `/api/v1/sessions/{session_id}/pricing` | Bearer | — | `PricingBreakdown` (formula, breakdown text) |
| GET `/api/v1/sessions/{session_id}/receipt` | Bearer | — | `SessionReceipt` |

### 2J. Payments
| Endpoint | Auth | Request | Response |
|----------|------|---------|----------|
| POST `/api/v1/payments/confirm` | Bearer | `{session_id, idempotency_key?}` | `{session_id, tx_hash, blockchain_ref, amount, already_paid}` |
| GET `/api/v1/payments/history` | Bearer | `offset?, limit?` | `{total_payments, payments}` |

### 2K. Micro-Slots
| Endpoint | Auth | Request | Response |
|----------|------|---------|----------|
| GET `/api/v1/micro/lots/{lot_id}/slots` | Bearer | `offset?, limit?` | `{lot_id, total_slots, available, reserved, occupied, prebooked, slots[]}` |
| GET `/api/v1/micro/lots/{lot_id}/slots/{slot_index}/probability` | Bearer | `target_time?` | `{slot_id, slot_label, probability, current_state, current_price}` |
| GET `/api/v1/micro/lots/{lot_id}/zones` | Bearer | `offset?, limit?` | `[{id, name, slot_count, available, occupancy_rate}]` |
| POST `/api/v1/micro/lots/{lot_id}/slots/seed` | Bearer+admin | — | `{status, count, total_slots}` |
| POST `/api/v1/micro/reserve` | Bearer | `{lot_id, slot_index, target_time?, idempotency_key?}` | `{reservation_id, slot_label, slot_id, probability, expires_at, status}` |
| POST `/api/v1/micro/release` | Bearer | `{slot_id, reservation_id}` | `{status, slot_id}` |
| POST `/api/v1/micro/prebook` | Bearer | `{lot_id, slots: [{slot_index, priority?}], target_time, idempotency_key?}` | `{prebook_id, lot_id, assigned_slot_index, slot_label, probability, price_at_booking, expires_at, status, fallback_order}` |
| POST `/api/v1/micro/confirm` | Bearer | `{prebook_id}` | `{session_id, prebook_id, slot_id, slot_index, slot_label, final_price, status}` |
| POST `/api/v1/micro/cancel` | Bearer | `{prebook_id}` | (cancels, refunds deposit) |
| GET `/api/v1/micro/prebooks/list` | Bearer | — | prebook records list |

### 2L. Wallet
| Endpoint | Auth | Request | Response |
|----------|------|---------|----------|
| GET `/api/v1/wallet` | Bearer | — | `{balance, currency}` |
| POST `/api/v1/wallet/topup` | Bearer | `{amount}` | `{balance, amount_added, message}` |

### 2M. Revenue
| Endpoint | Auth | Params | Response |
|----------|------|--------|----------|
| GET `/api/v1/revenue/cumulative` | Bearer+admin | — | `{total_revenue, total_sessions, total_lots, total_drivers, avg_revenue_per_session, avg_revenue_per_lot}` |
| GET `/api/v1/revenue/overview` | Bearer+admin | `days?(1-365)` | `{total_revenue, total_transactions, daily: [{lot_id, name, total_revenue, total_transactions, avg_daily_revenue}]}` |
| GET `/api/v1/revenue/transactions` | Bearer+admin | `offset?, limit?` | `[{tx_hash, lot_id, driver_id, action, amount, duration_minutes, status, timestamp}]` |

### 2N. Admin
| Endpoint | Auth | Params | Response |
|----------|------|--------|----------|
| GET `/api/v1/admin/dashboard` | Bearer+admin | — | `{total_lots, total_users, total_revenue, total_transactions, system_occupancy}` |
| GET `/api/v1/admin/system-health` | Bearer+admin | — | `{status, transactions_last_hour, occupancy_updates_last_5min, layers: {iot, ml, blockchain, rl, digital_twin, api}}` |

### 2O. Ingestion
| Endpoint | Auth | Request | Response |
|----------|------|---------|----------|
| POST `/api/v1/ingestion/occupancy` | Bearer | `{lot_id, occupied_slots, total_slots, net_flux?, sensor_id?}` | `{status, lot_id, occupancy_rate}` |

### 2P. Simulation (Time Machine)
| Endpoint | Auth | Request | Response |
|----------|------|---------|----------|
| GET `/api/v1/simulation/status` | Bearer | — | `{speedup, is_fast_forwarding, real_time, snapshot_exists}` |
| POST `/api/v1/simulation/speed` | Bearer+admin | `{speedup}` | (sets time acceleration) |
| POST `/api/v1/simulation/reset` | Bearer+admin | — | `{success, message}` |
| POST `/api/v1/simulation/snapshot` | Bearer+admin | — | `{success, message}` |

### 2Q. Health & Readiness
| Endpoint | Auth | Response |
|----------|------|----------|
| GET `/api/v1/health` | — | `{status, service, version, layers, dependencies}` |
| GET `/api/v1/ready` | — | `{ready, database, blockchain, models}` |
| GET `/` | — | SPA dashboard HTML |
| GET `/app/{page}` | — | Named template HTML (index, dashboard, driver, admin, login, app) |
| GET `/static/...` | — | Static files (CSS, JS) |
| GET `/docs` | — | Swagger UI |
| GET `/openapi.json` | — | OpenAPI 3.0 spec (76KB) |

---

## 3. IMPLICIT / BACKEND FEATURES

### 3A. Session Settlement (session_service.py)
- **Deposit model**: `BOOKING_FEE=$2` (non-refundable) + `DEPOSIT_RATE=1×` (refundable)
- **Grace period**: 15min free of charge
- **Stale reaper**: Sessions >24h in RUNNING auto-reaped on new session creation
- **Settlement**: `(elapsed - grace) × effective_price / 60`; refunds excess deposit to wallet; creates blockchain tx and outbox entry
- **Overcharge/Refund**: If charge > deposit → deduct from wallet; if charge < deposit → refund difference

### 3B. Micro-Slot State Machine (micro/state_engine.py)
- **5 states**: AVAILABLE → PREBOOKED → RESERVED → OCCUPIED → MAINTENANCE
- **TTLs**: RESERVATION_TTL=5min, PREBOOK_GRACE=30min, max prebook horizon=12h
- **Transition rules**: explicit matrix with thread-safe locking
- **Cleanup**: expired reservations/prebooks swept every 60s by background worker
- **Transition callbacks**: external notification on any state change
- **Slot types**: regular, handicap, ev, covered, premium — each with price modifier

### 3C. Bayesian Predictor (micro/predictor.py)
- **Beta-Binomial**: Beta(2,2) weakly informative prior, updated per occupancy event
- **Time decay**: long-horizon predictions mean-revert to 0.5
- **Override**: RESERVED→P=0.9, PREBOOKED→P=0.95, OCCUPIED/MAINTENANCE→P=0.0
- **Slot scoring**: `score = P × 10 - price × 0.05`
- **Per-slot pricing**: base_price × (1 + slot_type_modifier + demand_multiplier)

### 3D. No-Show Mechanism
- Prebook target time + grace window expires → status=`RESERVATION_NO_SHOW`
- Booking fee forfeited; deposit refunded minus 10% admin fee

### 3E. Wallet
- Balance: Float on User row (default 0.0)
- Topup: max $100k per topup
- Auto-deduction: on session settlement and prebook confirmation
- Transactions: full audit trail per wallet operation

### 3F. Outbox Pattern
- Tx dedup: SHA-256 hash prevents double-processing
- States: pending → delivered → failed
- Background worker: 60s interval, up to 200 items per pass, at-least-once delivery

### 3G. Background Workers (workers.py)
| Worker | Interval | Description |
|--------|----------|-------------|
| Miner | 300s | Mines pending blockchain transactions into blocks |
| Cleanup | 3600s | Removes old occupancy (72h), predictions, expired tokens, expired reservations |
| Outbox | 60s | Processes pending ledger outbox entries |
| Ingest | 60s | Simulates sensor ingestion (generates occupancy records) |
| All intervals | ÷ speedup | When time machine is active |

### 3H. Blockchain
- **PoW**: SHA-256, difficulty=2 (targets "00" prefix), nonce iteration
- **Genesis**: auto-created on init
- **SmartContracts**: base class with RevenueShareContract, AllocationContract
- **IPFS**: in-memory OrderedDict (max 1000, LRU eviction), SHA-256 CID, TTL-based GC
- **Persistence**: `data/blockchain.json`
- **Chain validation**: genesis integrity, hash linkage, difficulty compliance
- **Pending pool**: max 10k transactions

### 3I. IoT Sensor Fusion
- **DualSensorPair**: Ultrasonic (noise σ=0.05, 2% FP + 8% weather, 3% miss + 5% weather) + Vision (1% FP + 6% lighting, 2% miss + 8% lighting)
- **Fusion**: OR logic (occupied if either says occupied); consensus tracking
- **Weather factor**: 0.0–0.3 degrades sensor accuracy
- **Event extractor**: arrival/departure rates, net flux, turnover, anomaly (2σ CUSUM)

### 3J. Actuator Bridge
- **SmartBarrier**: open/closed/restricted/reservation-only
- **DigitalPricingBoard**: displays price, color-coded (green/yellow/red at 70%/85%)
- **SmartLighting**: dims with occupancy (0.3 + 0.7×rate)
- **CongestionLight**: green/yellow/red traffic light
- **Zone registry**: maps zone → actuator state for all zones

### 3K. ML Ensemble
- **Base**: RandomForest (500 trees, max_depth=12) + XGBoost (800 estimators, lr=0.02)
- **Meta**: RidgeCV (α in [0.01, 0.1, 1.0, 10.0]) on stacked predictions
- **Fallback chain**: meta → weighted avg (0.4RF+0.6XGB) → heuristic (occ_lag_15m)
- **Features**: 19 features — occupancy, lags, parking events, cyclical time, rolling stats
- **Training**: chronological 80/20 split, MAE metric, joblib persistence

### 3L. RL Training
- **NeuralAgent**: MLPRegressor(64,64), ε-greedy (ε=1.0→0.05, decay 0.98), replay buffer 2000, γ=0.95
- **Reward**: revenue + occupancy sweet-spot bonus - congestion penalty - price-gouging penalty
- **Warm-start**: 1000 synthetic examples with domain heuristics
- **Online**: 1200 episodes, mini-batches 64-128, target network hard-copy every 20 steps
- **MARL (QMIX)**: 6 agents, mixing network, 800 episodes

### 3M. Digital Twin
- **Simulator**: deque of TwinState (maxlen 1000), elastic demand: `Δocc = -α·price_mod·price/10 + N(0,σ)`
- **5 scenarios**: zone_closure, price_surge, capacity_expansion, weather_disruption, holiday_surge
- **Generator**: latent_dim=8, linear tanh projection, trained via MSE
- **Congestion**: normal (<50%), moderate (50-70%), high (70-85%), critical (>85%)

### 3N. Simulation Time Machine
- Speedup factor: 1× to 86400× (real-time to 1 year/hour)
- All worker intervals ÷ speedup
- Read/write isolation for DB snapshots

### 3O. Seed Data
- 21 lots across 10 cities (Birmingham, London, Manchester, New York, SF, Tokyo, Dubai, Singapore, Mumbai, Berlin)
- 14 users: 3 admins + drivers + guest + demo accounts
- 30 days of 15-min occupancy history
- 30 days of session history (80% settled, 10% cancelled, 10% running)
- Micro-slots per lot with row labels, type distribution (5% handicap, 5% EV)

### 3P. Rate Limiting
- `/api/v1/blockchain/transaction`: rate-limited
- `/api/v1/micro/prebook`: 5/min/driver
- Payment retry: up to 3 attempts with idempotency key

---

## 4. DATABASE TABLES (15)
`users`, `parking_lots`, `occupancy_records`, `transactions`, `parking_sessions`, `prediction_metrics`, `token_blacklist`, `ledger_outbox`, `micro_zones`, `micro_slots`, `slot_reservations`, `prebook_records`, `revenue_records`, `slot_state_log`

---

## 5. CONSTANTS / ENUMS
**Session**: running, pending_settlement, settled, cancelled
**Transaction**: pending, completed, failed
**Actions**: session_fee, payment, refund, deposit, booking_fee
**Payment**: card, cash
**Reservation**: active, used, cancelled, expired, refunded, no_show
**Slot**: regular, handicap, ev, covered, premium
**Layers**: iot, ml, blockchain, rl, digital_twin, actuator
**Congestion**: normal, moderate, high, critical
