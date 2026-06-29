# Pragmapark — AI Smart Parking Platform

> **Live app:** https://pragma-4szs.onrender.com
> **Landing & demo:** https://ashutoshgitmirror.github.io/pragmapark/
> **Whitepaper:** https://ashutoshgitmirror.github.io/pragmapark/pragmapark.pdf

A vertically integrated AI platform for smart parking management. Combines ensemble machine learning, deep reinforcement learning, blockchain-anchored transactions, digital twin simulation, and realistic IoT sensor fusion into a unified pipeline that forecasts occupancy, optimizes pricing, and actuates physical infrastructure in real time.

**Test credentials:** `driver@pragma.io` / `driver123` (driver) · `admin@pragma.io` / `admin123` (admin)

## Architecture

```
IoT ──▶ ML ──▶ Blockchain ──▶ RL ──▶ Digital Twin ──▶ Actuator
              └─── PipelineOrchestrator (session lifecycle)
```

| Layer | What it does |
|-------|-------------|
| **IoT** | Dual-sensor fusion (ultrasonic + vision) with realistic physics simulation (noise, dropout, drift, weather, occlusion) |
| **ML** | 15-min occupancy forecasting via RF + XGBoost + RidgeCV ensemble (MAE 0.030, R² 0.957) |
| **Blockchain** | SHA-256 PoW ledger, revenue-smart contracts, simulated IPFS off-chain store |
| **RL** | DQN neural pricing agent (pure NumPy MLP) + QMIX multi-agent coordination |
| **Digital Twin** | CVAE-WGAN generator with 5 counterfactual scenarios; STID spatial-temporal predictor |
| **Actuator** | Smart barriers, pricing boards, congestion lights — driven by RL pricing |

## Quick Start

```bash
# Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn src.api.server:app --reload --port 8800

# Frontend
cd frontend
npm install
npm run dev     # runs on :5173, proxies /api to Render backend

# Demo (Playwright walkthrough against local backend)
DISPLAY=:0 node demo.mjs
```

## Project Structure

```
src/
├── api/            # FastAPI (91 routes, 5 middleware layers, 17 migrations)
├── blockchain/     # PoW ledger, smart contracts, IPFS, pool manager
├── digital_twin/   # CVAE-WGAN generator, STID, scenario engine, DT simulator
├── features/       # 19-feature engineering (cyclical, rolling, flux, anomaly)
├── iot/            # DualSensorPair, realistic sensor simulator, actuator bridge
├── micro/          # 5-state slot FSM, Beta-Binomial predictor, slot pricing
├── models/         # RF + XGBoost + RidgeCV artifacts (31 MB total)
├── pipeline/       # PipelineOrchestrator (6-layer lifecycle), pricing controller
├── rl/             # NumPy DQN NeuralAgent, QMIX MARL, parking environment
├── main.py         # FastAPI entry point
└── constants.py    # Single source of truth for all enums, thresholds, features

frontend/src/       # React 18 + TypeScript + Vite 6 + Tailwind 3.4
├── api/            # Admin + driver API clients with types
├── components/     # UI components
├── pages/          # 9 admin + 8 driver pages (HashRouter, 18 routes)
└── context/        # AuthContext (JWT in HttpOnly cookies)

landing/index.html  # Static marketing page with embedded demo video

docs/typst/         # Whitepaper source (pragmapark.typ) + compiled PDF

tests/              # 48 unit/integration + 10 Playwright E2E (500+ passing)
demo.mjs            # Automated 71s Playwright demo walkthrough (9 shots)
```

## Demo Walkthrough

A 71-second headed Playwright script drives through the full driver lifecycle:

1. Portal & dashboard → 2. Scroll lot cards → 3. Find & select lot → 4. Pick slot → 5. Pipeline layer activation overlay → 6. Active session timer → 7. End & receipt → 8. Session history → 9. End card

Overlays at each stage explain the RL pricing agent, slot state machine, pipeline orchestration, closed-loop feedback, and blockchain audit trail.

```bash
DISPLAY=:0 NODE_PATH=/usr/local/lib/node_modules node demo.mjs
```

## API Overview

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/auth/login` | JWT auth (HttpOnly cookie) |
| `GET /api/v1/lots` | Parking lots with dynamic prices |
| `GET /api/v1/lots/{id}` | Lot detail + slot states |
| `POST /api/v1/sessions/start` | Start parking session |
| `POST /api/v1/sessions/end` | End + settle session |
| `GET /api/v1/sessions/active` | Active session for user |
| `GET /api/v1/sessions/history` | Past sessions |
| `POST /api/v1/predict/occupancy` | ML occupancy forecast |
| `GET /api/v1/blockchain/chain` | Full blockchain ledger |
| `POST /api/v1/prebooks/create` | Create advance booking |
| `POST /api/v1/prebooks/confirm` | Confirm prebook |
| `GET /api/v1/admin/dashboard` | Admin metrics |
| `POST /api/v1/admin/lots` | CRUD lots (admin) |

Full API: 91 routes across sessions, lots, payments, prebooks, admin, blockchain, IoT ingestion, digital twin, and alerts.

## License

MIT
