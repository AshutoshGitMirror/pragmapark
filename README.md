# Smart Parking — 6-Layer Hybrid AI System

## Project Status: OPERATIONAL
Full 6-layer hybrid smart parking platform: **IoT → ML → Blockchain → RL → Digital Twin → Actuator**.

### 1. IoT Layer
Dual-sensor fusion (ultrasonic + vision) with weather-aware noise models. `DualSensorPair` provides consensus occupancy and false-positive rate per lot.

### 2. ML Prediction Layer
RF + XGBoost ensemble (40/60 weighted), meta-learner stacking when available. 19-column feature pipeline with rolling windows, CUSUM change-point detection, and cyclical time encoding. 97.2% accuracy (MAE 0.028) at 15-minute horizon.

### 3. Blockchain Layer
SHA-256 proof-of-work ledger with difficulty-2 mining, IPFS off-chain store (content-addressed FIFO cache), PoolManager for revenue-sharing pools, and SmartContracts for revenue distribution and spot allocation. Ledger outbox pattern for at-least-once delivery.

### 4. RL Pricing Layer
Deep Q-Network agent (MLPRegressor 64×64) with epsilon-greedy exploration. Behavioral cloning on synthetic market data → online policy optimization (1200 episodes). Reward balances revenue, sweet-spot occupancy (60-80%), and anti-gouging penalty. Price range $5-$50.

### 5. Digital Twin Layer
Multi-zone elasticity simulator with congestion-level classification (normal/moderate/high/critical). 5 counterfactual scenarios (zone closure, price surge, capacity expansion, weather, holiday spike). Neural generator for synthetic scenario creation.

### 6. Actuator Layer
`ActuatorBridge` controls `SmartBarrier`, `DigitalPricingBoard`, and `CongestionLight` per zone. Threshold-based actuation at 0.85 (red/restricted), 0.70 (yellow), 0.50 (green) occupancy.

---
## How to Run

| Mode | Command | Description |
|---|---|---|
| API server | `python3 src/main.py api` | FastAPI on :8000 |
| Full hybrid loop | `python3 src/main.py hybrid` | 6-layer demo |
| RL training | `python3 src/main.py rl` | Phase 1+2 training |
| MARL training | `python3 src/main.py marl` | Multi-agent RL |
| Chrono analysis | `python3 src/main.py chrono` | Forecast verification |
| Dashboard | `python3 src/main.py dash` | Plotly Dash on :8050 |
| Retrain all | `bash scripts/retrain.sh` | ML + RL + MARL |
| Seed demo data | `python3 scripts/seed_data.py` | 21 lots, 2 users, 90d history |
| E2E test suite | `bash scripts/round_trip_test.sh` | 93 integration tests |

## Observability

Logs are emitted to stderr via the standard Python `logging` module (`import logging; logger = logging.getLogger(__name__)`). No custom log format — uvicorn's default handler prints `LEVEL:name:message`.

### Event name prefixes (greppable with `rg "event="`)

| Prefix | File | Purpose |
|---|---|---|
| `blockchain.save.` | `src/blockchain/ledger.py` | Chain persisted to disk |
| `blockchain.load.` | `src/blockchain/ledger.py` | Chain loaded from disk / integrity check |
| `pools.load.` | `src/blockchain/pool_manager.py` | Pool state loaded / corrupt allocations skipped |
| `pools.persist.` | `src/blockchain/pool_manager.py` | Pool state saved to disk |
| `ipfs.pin.` | `src/pipeline/orchestrator.py` | IPFS off-chain pin attempt |
| `ledger.flush.` | `src/pipeline/orchestrator.py` | Blockchain flush + recovery on failure |
| `outbox.json.parse.` | `src/api/ledger_outbox.py` | Outbox payload JSON parse failure |
| `sessions.start.` | `src/api/routes/sessions.py` | Session start handler failure |
| `sessions.end.` | `src/api/routes/sessions.py` | Session end handler failure |
| `shutdown.blockchain.` | `src/api/server.py` | Shutdown-time pending-tx flush |
| `periodic.miner.` | `src/api/server.py` | Background block miner (every 300s) |
| `periodic.cleanup.` | `src/api/server.py` | Background data retention cleanup (3600s) |
| `periodic.outbox.` | `src/api/server.py` | Background outbox flush (60s) |
| `periodic.ingest.` | `src/api/server.py` | Background ingest simulation (60s) |
| `readiness.*.` | `src/api/server.py` | Health-check DB / blockchain / model failures |
| `rl.agent.` | `src/rl/train_control.py` | RL agent artifact save |
| `hybrid.*.` | `src/hybrid_loop.py` | Hybrid loop model/agent load failures |
| `pricing.heuristic.` | `src/pipeline/pricing.py` | RL agent unavailable → heuristic fallback |
| `migrations.` | `src/api/database.py` | Alembic migration applied / fallback |
