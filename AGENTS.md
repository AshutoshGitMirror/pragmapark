# PRAGMAPARK — AI Smart Parking Platform · Project Memory

> **This file is the project's survivable memory.** Read it in full on first load.
> UPDATE it after every significant change (bug fix, refactor, architecture change,
> dep update, deploy). Do NOT delete it. If a fact can't be verified, mark it "unverified".
> Keep it TERSE — no ASCII-art tables (they triple byte size and trigger auto-compaction).

---

## 0. Rebuild & Init (packages purged to save ~1.5 GB)

```
pip install -r requirements.txt          # Python deps (~1.3 GB)
cd frontend && npm install               # Frontend deps (~171 MB)
```
`.venv/` and `frontend/node_modules/` are gitignored and safe to delete.

- **Python (16 deps):** scikit-learn>=1.8,<1.9 · xgboost>=2.0 · pandas>=2.0 · numpy>=1.24 · fastapi>=0.100 · uvicorn>=0.22 · pydantic[email]>=2.0 · joblib>=1.3 · sqlalchemy>=2.0 · python-jose[cryptography]>=3.3 · passlib[bcrypt]>=1.7 · bcrypt>=4.0,<5.0 · python-multipart>=0.0.6 · psycopg2-binary>=2.9 · alembic>=1.12 · pytest>=9.0
- **Frontend (14 deps):** react/react-dom ^18.3.1 · react-router-dom ^7.16 · axios ^1.17 · recharts ^2.15.4 · framer-motion ^11.15 · leaflet ^1.9.4 · react-leaflet ^4.2.1 · gsap ^3.12.5 · three ^0.170 · (dev) vite ^6.0.3 · typescript ^5.6.3 · tailwindcss ^3.4.16

---

## 1. Identity & Deploy

- **Name:** Pragma (Pragmapark). Hybrid smart parking from IEEE `paper.tex`: IoT + ML + Blockchain + RL + Digital Twin + Actuator.
- **Root:** `/home/RatAnon/AI-MultiAgent-Land/Project_Folders/gemini_smart_parking_pro/`
- **Whitepaper:** `docs/typst/pragma_whitepaper.typ` (ground-truth architecture doc).
- **Deploy:** Render service `pragma` (`srv-d8bvbuv7f7vs73cs0tu0`) serves BOTH the FastAPI API AND the React SPA → https://pragma-4szs.onrender.com
- GH Pages (https://ashutoshgitmirror.github.io/pragmapark/) is ONLY the static marketing/landing page (`landing/index.html`) — NOT the SPA.
- **Deploy flow:** push `main` → CI runs. `lint`/`test`/`e2e`/`security` (bandit) jobs ALL PASS (post A113 — the 15× B108 `/tmp` in tests/ are fixed), so `checksPass` goes green and Render **auto-deploys** (`autoDeploy=yes`, `autoDeployTrigger=checksPass` on srv `srv-d8bvbuv7f7vs73cs0tu0`, confirmed via API). Historically deploys looked manual (504301f, e1a4f01, b813ce1) ONLY because the failing bandit job kept `checksPass` red. `render.yaml` has NO `autoDeploy` key, so the dashboard setting governs. **Do NOT** `render_trigger_deploy` a SHA that already has a build — it deploys on its own once green.
- **Seed creds:** `driver@pragma.io`/`driver123` · `admin@pragma.io`/`admin123` (whitepaper mentions `planner@pragma.io`/`planner123`).

### Filesystem topology
- `src/api/` FastAPI: routes, schemas, services, auth · `src/blockchain/` SHA-256 PoW ledger, contracts, IPFS, pool · `src/constants.py` SINGLE SOURCE OF TRUTH for enums/thresholds · `src/digital_twin/` CVAE-WGAN, STID, scenarios, DT sim · `src/features/` builder.py, engine.py · `src/iot/` DualSensorPair, RealisticParkingSensorSimulator, actuators · `src/micro/` slot state_engine.py, predictor, pricing · `src/models/` ML artifacts · `src/pipeline/` PipelineOrchestrator singleton · `src/rl/` NumPy DQN, QMIX · `src/simulation/` time_machine.py · `src/cv/` local YOLOv8 CV agent (local-only, never imported by Render backend)
- `frontend/src/`: `api/` (client.ts admin, driverClient.ts, cvClient.ts, types.ts) · `components/` · `pages/` (9 admin + 8 driver + layouts) · `App.tsx` (18 routes + ErrorBoundary)
- `tests/`: `e2e/` Playwright (10 files) + `*.py` unit/integration · `data/`: raw CSV, blockchain.json, ipfs_store.json, pragma.db (SQLite dev), snapshots/

---

## 2. Architecture (6-layer hybrid pipeline)

Client (React SPA + REST) → **PipelineOrchestrator** singleton fans out to 6 layers → Actuator layer → Persistence (PostgreSQL on Render / SQLite dev, Alembic migrations, in-memory SlotStateEngine + BlockchainLedger + IPFS + rate limiter).

### Layer files & verified claims
- **IoT** — `iot/sensors.py`(163) DualSensorPair fusion · `iot/generator.py`(220) RealisticParkingSensorSimulator (replaces old `np.random.binomial(1,0.5)`): diurnal/weekly peaks (9AM/6PM weekdays), entrance-proximity `P(occ_i)=sigmoid(15*(rate−i/N))`, ultrasonic physics (2.0m threshold, noise, dropout, drift), camera ambient-light/weather/occlusion, seasonal weather + storm bursts (`days%4==0`), tracks false positives via `us_occupied != vis_occupied` · `iot/actuators.py`(176) · `api/routes/ingestion.py`(177) `POST /ingestion/sensor-readings`.
- **ML** — `features/builder.py`(79) X_COLS · `features/engine.py`(236) raw→feature (inference uses `occ.iloc[:-(N+1):-1]` to match training `.shift(1)`) · `models/train_real.py`(122) RF(100)+XGB(200)+RidgeCV · `pipeline/predictor.py`(78) lazy-loads · `api/routes/prediction.py`(184). **19 features** (`constants.EXPECTED_FEATURE_COLS`): occupied_slots, total_slots, occ_lag_15m, occ_lag_1h, pe_net_flux, pe_arrival_rate, pe_departure_rate, pe_turnover, pe_anomaly, pe_change_point, hour_sin, hour_cos, hour_sq, dow_sin, dow_cos, is_weekend, occ_roll_mean_3h, occ_roll_std_3h, occ_acceleration. Models lazy-loaded (Render OOM fix); artifacts rf=30MB/xgb=958KB/meta=618B; retrain MAE 0.0299; sklearn pinned ≥1.8,<1.9.
- **Blockchain** — `ledger.py`(229) SHA-256 PoW + JSON persist (`data/blockchain.json`) · `contract.py`(88) RevenueShareContract 90/10 (called on every `process_payment()`) · `ipfs.py`(130) OrderedDict cap 1000 + JSON persist · `transaction.py`(57) · `pool.py`(87) · `pool_manager.py`(142) singleton · `api/ledger_outbox.py`(78) `process_pending()` calls `flush_ledger()` even with no outbox items.
- **RL** — `agent.py`(183) NeuralAgent: pure NumPy 3-layer MLP 64×64 (ZERO sklearn), input(state+action)→W1(64)→ReLU→W2(64)→ReLU→W3(1), He init, manual backprop, Adam(b1=.9,b2=.999), target net sync every 20 steps, replay deque(2000) batch 128, ε 1.0→×.98→min .05 · `multi_agent.py`(321) QMIXMARL hypernetwork mixer (softmax weights → `Q_tot=Σ w_i·Q_i + b(s)`), CV routing, per-episode reset (`cv.routed=False`, `cv.travel_time=0`) · `environment.py`(62) · `train_control.py`(129).
- **Digital Twin** — `simulator.py`(189) DT zones + STID · `generator.py`(318) CVAE-WGAN (state_dim 5, cond_dim 6, latent 8, hidden 16; encoder→{mu,logvar}; decoder→4-dim state; CVAE loss MSE+0.05·KL; WGAN critic + gradient penalty λ_gp=10, n_critic=3; `online_update(n_share_listed)` builds 5-col sample; `synthesize_scenario()` returns 4-elem) · `scenario.py`(287) 6 counterfactuals: zone_closure, price_surge, capacity_expansion, weather_disruption, holiday_spike, resident_share_adoption · `stid.py`(138) 100-zone, spatial+temporal emb(8), spatial_corr(Z×Z), MLP(33), manual GD. `end_session()` sets zones[lot]["occupancy"/"price"]=real, calls `dt.tick()` + `generator.online_update()` (feeds share_count from slot_resident_mapping).
- **Actuator** — `iot/actuators.py`(176) SmartBarrier (congestion-gated), PricingBoard (RL/surge), CongestionLight, ActuatorBridge (`actuate(lot,occ,price,mult)`, auto-registers zones). Wired in `orchestrator.py`(423): start_session activates `[iot,ml,blockchain,rl,actuator]`; end_session `[blockchain,rl,digital_twin,actuator]`.

---

## 3. Quantified metrics (audited 2026-06-23, post-purge unless noted)

Python src files 73 · Python src lines 12,920 · test files 51 · test lines 14,400+ · residential tests 56 · e2e files 10 · frontend files 33 · frontend lines 6,401 · total ~24,000 · passing tests (no e2e) 500+ · flake8 50 (all E501 cosmetic) · pyright src/tests 0/0 · bandit High src 0 / Medium src 0 / Medium tests 0 (B108 /tmp fixed A113) · tsc 0 · `# type: ignore` src 3 / tests 6 (all typeshed) · frontend build 16s · main chunk 1.27 MB · **git commits ahead 0 (all pushed; live b813ce1)** · ML MAE 0.02991 R² 0.9573 · prod after purge: 2 users / 2 lots / 3 sessions · whitepaper 1,011 lines, fidelity 9.5/10 · alembic migrations 17 · API routes 91 · middleware 5.

---

## 4. Bug fix log (all VERIFIED CLOSED)

Terse: `ID — cause → fix`.

- **A1** — end_session wrong unit → `entry_price*duration_hours`; final_price→current_rate.
- **A2** — prebook refund `status ==` → `.in_([RESERVATION_ACTIVE, RESERVATION_CONFIRMED])`.
- **A3** — RL status → use `pipeline.pricing.agent_available` not `hasattr(pipeline,'rl')`.
- **A4-A5** — PG compat: `db_extract_hour()`/`db_date()` replace `EXTRACT()`/`DISTINCT ON`.
- **A6** — Decimal×float → cast `float(sess.entry_price)` before multiply.
- **A7** — return key mismatch final_price→current_rate + compat reader.
- **A8** — feature drift `hour_linear`→`hour_sq` to match pre-trained models.
- **A12** — IoT sim `np.random.binomial` → RealisticParkingSensorSimulator.
- **A13** — SQLite snapshot: `engine.dispose()` before `shutil.copy2`.
- **A14** — orphaned ScenarioEngine removed; routes use pipeline instance.
- **A15** — consensus: fused occ from `clean_reading().mean()` not `consensus_occupancy()`.
- **A16** — actuator loop: `actuate()` wired into start_session + end_session.
- **A17-A18** — scenarios: CVAE refactor, 5 scenario-conditional generation.
- **A19** — session gen creates SlotStateLog entries.
- **A20** — slot 0/1-based → 1-based consistently across seed/API.
- **A21** — SlotPredictor `free`→`available` directional signal fix.
- **A22** — STID zero feedback → 30% blend into simulated occupancy.
- **A23** — cleanup transitions: `_on_transition` called in all 3 methods.
- **A24** — hardcoded alerts removed from `/admin/alerts`.
- **A41** — timer `645:52`→HH:MM:SS on ActiveSessionPage.
- **A42-A43** — countdown `1057m`→format + `useRef(onExpire)` fix.
- **A44** — FindPage error banner in slot picker + active-session check.
- **A45** — axios interceptor retries 502/503/504 up to 2×.
- **A46** — blockchain stuck → `flush_ledger()` even without outbox items.
- **A47** — `fetchActiveSession` re-throws non-404 (was swallowing 500s).
- **A48** — 5 silent excepts → `logger.warning/critical(exc_info=True)`.
- **A49** — MicroSlotGrid optional `lotId` prop (was hardcoded A1).
- **A50** — deleted orphan 0-byte `fallbackData.ts`.
- **B25** — test_workers_stress: assert dedented to post-loop.
- **B26** — `clr()` guards `hasattr(lim,'_buckets')` for DBRateLimiter.
- **B27** — pyright tests/ 36→0 across 7 files.
- **B28** — 4 silent except → `logger.exception`.
- **B29** — added Referrer-Policy + Permissions-Policy headers.
- **B30** — SPA file reads: try/except FileNotFoundError → 503.
- **B31** — `print()`→`logger.info()` in digital_twin/simulator.py.
- **B32** — 13 ts-unused → 0; enabled noUnusedLocals/Params.
- **B33** — migration 0016 PK: dialect-specific SQLite batch vs PG ALTER.
- **B34** — DBRateLimiter: SQLite returns False, PG retries once.
- **B35** — PG tz: 11 column defaults stripped via `.replace(tzinfo=None)`.
- **B36** — SlotCurrentState unique index via `__table_args__` not Column.
- **B37** — alembic check CI: stamp head before check (version table loss).
- **A51** — IntersectionObserver crash (framer-motion non-numeric threshold) → wrap ctor in try/catch in main.tsx.
- **A52** — PortalSelectorPage bloat: removed redundant marketing components below selector cards.
- **A53** — landing page: 5 fake-interactive autoplay sim sections → clean feature grid + CTA.
- **A54** — prod seed missing: added `PRAGMA_ADMIN_SEED=true` to render.yaml.
- **A55** — corrupted bcrypt hash → login 500 not 401; wrapped verify_password in try/except + `/api/v1/auth/seed`.
- **A56** — passlib×bcrypt 5.0 break → pinned `bcrypt>=4.0,<5.0`.
- **A57** — removed seed_data.py (159L), auto-seed, /auth/seed endpoint (no tests depended).
- **A58** — removed 9 orphaned frontend components (~1,700 L).
- **A59** — deleted dead `pipeline/hybrid_loop.py` (179 L) + 10 empty dirs.
- **A60** — full E2E audit on Render: 9 admin + 14 driver features OK, full cycle + reserve OK, 0 bugs.
- **A61** — prod DB purge (18 users, 4 lots, 12,225 sessions, etc.); kept 2 lots/2 users/3 sessions.
- **A62** — ML retrained on Birmingham CSV (35,322 rows), MAE 0.02991 R² 0.9573, git-tracked.
- **A63-A74** — UX + Session 7-8 sweeps (see git history; details condensed).
- **A75** — admin sidebar scroll gradient fade when overflowing.
- **A76** — reserve modal past-date → 'Arrival time must be in the future' validation.
- **A77** — filter empty state 'No handicap lots available' + Clear filter.
- **A78** — payment 'Processing...' amber 'taking longer' after 15s.
- **A79** — ErrorBoundary auto-reloads on ChunkLoadError (was stale retry loop).
- **A80** — chunk-load 404 after deploy → global ErrorBoundary + cache-control chain.
- **A81** — admin bcrypt hash corrupted on deploy → direct `passlib.hash()` update in prod DB.
- **A82** — blockchain mining held global lock → moved PoW to background worker; endpoints return immediately.
- **A83** — added 15s amber slow-load warning to ALL 6 'Processing' buttons.
- **A84** — admin ParkingLotsPage: added Edit/Delete CRUD + city/lat/lng + delete confirm.
- **A85** — MicroSlotsPage: search + state filter + click-inspect modal + 15s auto-refresh + error handling.
- **A86** — AlertsPage resolve button visible on mobile + no longer swallows errors.
- **A87** — added Escape-close to 2 modals (delete confirm, slot inspect).
- **A88** — ParkingLotsPage error state: added retry button.
- **A89** — added confirmation to End Parking / Cancel Booking / Sign Out (driver+admin).
- **A90** — NaN when ML fails: added `?? 0` at all 7 `predicted_occupancy` sites.
- **A91** — FindPage: added Retry buttons to slot-picker + warmup-timeout errors.
- **A92** — TransactionsPage `-$0.00`: '-' prefix only when `amount > 0`.
- **A93** — role-switch blocked by auth redirect → sign-out notice with switch/portal options.
- **A94** — duration floor `max(dur,0.1)` inflated short sessions → removed floor.
- **A95** — mobile responsive: added sm:/lg: to 6 grids + RevenuePage empty state.
- **A96** — whitepaper Typst 0.12 API: `color.transparentize()`→`.transparentize()`; pipeline table cleaned.
- **A97** — demo script 9/9 shots pass on Render (70s), prelude seeds 2 history sessions.
- **A98** — DT state expansion (state 4→5, cond 5→6): TwinState `n_share_listed`, resident_share_adoption scenario, `GET /digital-twin/state`, `GenerateScenarioResponse.shared_occupancy`; missing constants added. 14 DT tests pass.
- **A99** — residential share-parking test suite ADDED (3 files, 57 tests). Gotchas: contract state dict lazy-adds keys (use `.get(key,0)` deltas); LotCreateResponse has only status+lot_id (verify slots via `GET /lots/{id}/slots`); DELETE /vehicle needs active permit (unregister before deactivate).
- **A100** — Real CV module Phase 1: `src/cv/{roi,ultrasonic,detector,agent,cli}.py` + requirements-cv.txt (torch/ultralytics, LOCAL ONLY). First real signal (vision). Auth = per-sensor API key (X-Sensor-Key). Ingest real vision + `ultrasonic_readings=[False]*n` → fuse branch. 18 offline geo tests pass. ty LSP errors = uninstalled-dep false pos.
- **A101** — plan persisted `.opencode/plans/cv_module_plan.md` (D1-D9 locked decisions).
- **A102** — per-sensor API-key auth: Sensor ORM (database.py), sensor_auth.py, schemas/sensor.py, routes/sensors.py (CRUD ownership-enforced), ingestion X-Sensor-Key branch + JWT fallback, alembic 0018 create sensors, cv agent/cli use CV_SENSOR_KEY/CV_LOT_ID. 10 tests pass. Committed 9384df0; Sensor ORM actually landed in a1a9dd5.
- **A103** — Phase 2 "Live Vision" admin page: `src/cv/agent.py` CameraManager + endpoints (mjpeg/frame/occupancy/calibrate); graceful cv2-absent placeholder JPEG. Frontend `cvClient.ts` + `LiveVisionPage.tsx` + route + sidebar. 36 pytest / tsc 0. Pushed a1a9dd5. "Synced to cloud" indicator deferred.
- **A104** — driver `/lots` HTTP 500 PROD-only: `OccupancyRecord.occupancy_rate` NULLable in prod PG (migration omitted NOT NULL) but ORM `nullable=False`; SQLite enforced it so unreproducible locally. `lot_to_summary` (utils.py) `*100` + driver.py search/detail deref NULL → TypeError before predict. Fix: guard every `latest.occupancy_rate`/`.price` deref with `is not None` → 0.0/base_price.
- **A105** — NULL-deref hardening sweep + root-cause migration: guarded ALL occupancy_rate/price derefs (utils, driver, admin ×6, sessions, DT state+chart, micro/zones); fixed DashboardPage.tsx `$`→₹ (lines 271/274); added alembic `0019_enforce_occupancy_rate_not_null` (backfill NULL→0.0, SET NOT NULL, dialect-aware; price stays nullable).
- **A106** — frontend currency sweep (literal `$`+digit): fixed ActiveSessionPage:157, ParkingLotsPage:262, ResidentManagementPage:222, DashboardPage:362/364 → ₹; added ₹ to RevenuePage:44/54.
- **A107** — backend `float(None)` crash sites (nullable-by-design): orchestrator.simulate_ingest, DT simulator, pricing.py loop, wallet.py → guarded `is not None`.
- **A108** — test baseline 2026-07-18: ~511 pass, 6 fail = environmental (3× test_workers_stress AF_UNIX fork; 3× residential E2E time-of-day). NOT regressions.
- **A109** — currency gap closed via LIVE prod audit (A106 missed `$`+`{` template): fixed AnalyticsPage:246, ResidentManagementPage:149, ShareParkingPage:132/160/234 → ₹. Zero `$` currency remains.
- **A110** — driver `/lots` HTTP 500 PROD (data-driven None on required pydantic field → unlogged ResponseValidationError). Fix: `DriverLotSearchItem`/`DriverLotDetail` numeric fields Optional-with-default; `search_lots` try/except degrades to un-enriched summaries (never 500); `orchestrator.driver_search_lots` coerces NaN/None via `np.nan_to_num`. Verified live 200.
- **A111** — CI test/e2e time-of-day flakiness in test_residential.py (booked `now+3h` vs 06:00-22:00 window). Fix: MODULE-LEVEL `_future` lands mid-window (12:00 UTC + offset, +1 day if needed); removed broken `_freeze_now` (datetime immutable).
- **A112** — THE real CI test/e2e blocker: migration 0018 passed `ForeignKeyConstraint` as a COLUMN arg → `assert isinstance(table, Table)` on fresh PG, so `alembic upgrade head` failed before pytest. Fix: moved both FKs to TABLE level in `0018_create_sensors.py`. Fresh DB now runs 0001→0019 clean. Verified live `GET /api/v1/driver/lots` → 200.
- **A113** — CI `security` (bandit) job FAILED pre-existingly on 15× B108 (hardcoded `/tmp` in tests/): `conftest.py`, `persona_brenda.py`, `the_people_vs_parking.py`, `user_sim_test.py`, `stress_test.py` (env-var dirs + `os.listdir`/`os.remove` cleanup), `test_ledger.py` + `test_pricing_controller.py` (nonexistent-file paths). Fix: replaced all literal `/tmp/...` with `tempfile.gettempdir()`/`os.path.join(tempfile.gettempdir(), ...)`. Bandit now 0 B108 CLEAN; affected pytest files still 100% pass.

---

## 5. Known limitations (architectural trade-offs, NOT bugs)

- Full test suite 120s+ → run `--ignore=tests/e2e`, timeout 60-120s; individual files <30s.
- PipelineOrchestrator global lock (DBLock) serializes 6 sites — DB-level fix out of scope.
- Singleton in-memory state (blockchain, slot_state_engine, rate_limiter, digital_twin) prevents horizontal scale — cannot run `--workers > 1`.
- Render free tier OOM tight (models 149MB→31MB + lazy-loaded, 512MB ceiling).
- Frontend main chunk 1.3MB — needs code-split via dynamic `import()`.
- **Render free tier HIBERNATES:** first request after idle returns 503 (`x-render-routing: hibernate-pending-wake`) + ~20-60s cold boot spinner. NOT a bug — WAIT & reload (~25s) before judging the live deploy.
- **agent-browser MCP is NOT bash-sandbox-network-constrained** — it reaches onrender.com directly (bash blocks curl/pip/rtk egress). Use it to audit the LIVE deploy (it caught the A106/A109 currency gap that local grep missed).

---

## 6. Security & auth

- **Headers:** X-Content-Type-Options nosniff · X-Frame-Options DENY · HSTS (HTTPS-conditional) · X-XSS-Protection 0 · CSP (nonce dash / strict SPA) · Referrer-Policy strict-origin-when-cross-origin · Permissions-Policy geolocation/camera/microphone=() · Server header stripped · Cache-Control no-store for `/api/` · X-Request-Id per request.
- **Auth:** JWT in HttpOnly cookies (`set_auth_cookie` in auth.py). Admin + driver both use `withCredentials:true`. No localStorage tokens. Login = `POST /api/v1/auth/login` (role-agnostic; NO `/auth/driver/login` — 404s).
- **Rate limiting:** TokenBucket (in-memory per-key) + DBRateLimiter (PG `FOR UPDATE`, SQLite rejects races). Global 200 calls / 60s.

---

## 7. OPERATING MODE — mandatory rules for every agent

1. **READ CODE YOURSELF.** Subagents are for discovery (find/grep) only. If you didn't read it, you don't know it.
2. **VERIFY BEFORE REPORTING.** Measure, don't assume. Don't copy stale metrics. If unverifiable, say "unverified".
3. **FIX ON SIGHT, ASK LATER.** Fix bugs you find; if you can't, document here. Only ask permission for destructive ops (rm -rf, billing, delete infra, breaking migration).
4. **SUBAGENTS ARE TOOLS, NOT BRAINS.** Architecture/correctness judgments are YOUR job.
5. **UPDATE THIS FILE IMMEDIATELY ON ANY CHANGE** (bug → Sec 4, layer → Sec 2, tests → Sec 3, deploy → Sec 1). Keep entries TERSE.
6. **DO NOT DELETE THIS FILE** (git-tracked on purpose). Update, don't remove.
7. **LOCAL TEST ENV GOTCHAS** (2026-07-18):
   - Bare `python3`/`pip` are sandbox shims (no deps). Use `./.venv/bin/python` + `./.venv/bin/pip`.
   - Sandbox BLOCKS `AF_UNIX` → run Postgres over TCP: `unix_socket_directories=''`, `listen_addresses='127.0.0.1'`, `port=5432`; connect `postgresql://pragma@127.0.0.1:5432/...` (never a `/tmp/.s.PGSQL` socket).
   - PG daemon is REAPED between separate bash calls → start PG **and** run pytest in ONE combined command.
   - `test_workers_stress.py` (3 tests) fails here with `PermissionError ... AF_UNIX` (forkserver) — SANDBOX-only, passes on real CI. Not a regression.
   - `datetime.datetime` is IMMUTABLE — can't monkeypatch `now()`. Use a module-level helper (see A111 `_future`).
   - Login endpoint `/api/v1/auth/login` (role-agnostic); `/api/v1/auth/driver/login` 404s.

---

## 8. Constants reference

`src/constants.py` (232 lines) is the SINGLE SOURCE OF TRUTH — **never hardcode; import from it**: session statuses (SESSION_RUNNING, SESSION_PENDING_SETTLEMENT…), reservation statuses (RESERVATION_ACTIVE/CONFIRMED…), tx actions (TX_ACTION_SESSION_FEE/BOOKING_FEE…), `EXPECTED_FEATURE_COLS` (19), `cyclical_time_features()`, IoT thresholds (CONGESTION_HIGH 0.85 / MODERATE 0.70), pricing (DEFAULT_BASE_PRICE 10.0, DEFAULT_PRICE_CAP 200.0), FREE_GRACE_MINUTES 15, BOOKING_FEE 2.0, DEPOSIT_RATE 1.0, LAYER_NAMES `[iot,ml,blockchain,rl,digital_twin,actuator]`, `heuristic_price_multiplier()`, HOLIDAYS + `is_holiday()`, `hour_sq=(hour-12)^2/144`, slot-type distribution thresholds, SlotPredictor consts (PRIOR_PROBABILITY 0.5), residential (SHARE_BOOKING_ACTIVE, PERMIT_MONTHLY, VEHICLE_ID_PATTERN, SHARE_*, PERMIT_RATES).

---

## 9. Key file directory

`pipeline/orchestrator.py`(423) all 6 layers · `api/server.py`(908) 91 routes/5 middleware · `api/database.py`(557) SQLAlchemy/Alembic · `api/routes/sessions.py`(481) · `api/routes/admin.py`(422) · `api/routes/lots.py`(483) · `api/routes/micro/prebooks.py`(489) prebook lifecycle · `api/services/session_service.py`(286) settlement/refund · `api/utils.py`(317) auth/rate/security · `api/workers.py`(243) miner/cleanup/outbox/ingest · `micro/state_engine.py`(460) · `micro/predictor.py`(154) Beta-Binomial · `digital_twin/{generator 318, simulator 189, scenario 287, stid 138}` · `rl/{agent 183, multi_agent 321}` · `iot/{generator 220, sensors 163, actuators 176}` · `features/{engine 236, builder 79}` · `blockchain/{ledger 229, contract 88, ipfs 130}` · `simulation/time_machine.py`(199) · `constants.py`(232) · `frontend/src/App.tsx` 18 routes · `landing/index.html`. (seed_data.py deleted 2026-06-20.)

---

## 10. Demo script

`demo.mjs` (~1,595 lines). Runs against LOCAL backend (port 8800, SQLite `data/pragma.db`) or Render if healthy. Prelude (unrecorded): login → seed 2 ended sessions. 9 shots (portal→find→select→start→active→end→history→end card) with body-injected overlays (RL Pricing, Slot State Machine, Pipeline Activation, Closed-Loop Feedback, Audit Trail; 4s min each). ~81.5s dry-run passed 2026-06-28. Run: `NODE_PATH=/usr/local/lib/node_modules node demo.mjs` (needs local backend + built frontend dist).

---
*END — if you're an agent reading this, UPDATE the sections above when anything changes.*
