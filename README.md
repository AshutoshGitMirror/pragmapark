# Pragma — AI Smart Parking Platform

> **Live demo:** https://ashutoshgitmirror.github.io/pragmapark/

Pragma is a vertically integrated AI platform for smart parking management. It combines ensemble machine learning, deep reinforcement learning, blockchain-anchored transactions, digital twin simulation, and IoT sensor fusion into a unified six-layer pipeline that predicts occupancy, optimizes pricing, and coordinates physical infrastructure in real time.

## Architecture

```
IoT ──▶ ML ──▶ Blockchain ──▶ RL ──▶ Digital Twin ──▶ Actuator
```

| Layer | What it does |
|-------|-------------|
| **IoT** | Dual-sensor fusion (ultrasonic + vision) for reliable occupancy detection |
| **ML** | 15-min occupancy forecasting via stacked RF + XGBoost + RidgeCV ensemble |
| **Blockchain** | PoW SHA-256 ledger, smart contracts, simulated IPFS off-chain storage |
| **RL** | DQN-based neural pricing agent (single + QMIX multi-agent) |
| **Digital Twin** | Agent-based zone simulation with counterfactual scenarios |
| **Actuator** | Barrier, pricing board, and congestion light commands |

## Tech Stack

**Backend** — Python 3.11+, FastAPI, SQLAlchemy, Alembic, scikit-learn, XGBoost, Joblib

**Reinforcement Learning** — DQN via MLPRegressor (64×64), QMIX multi-agent coordination, epsilon-greedy exploration, replay buffer

**Blockchain** — Custom SHA-256 PoW chain, smart contracts (revenue share, allocation), simulated IPFS store

**Digital Twin** — Agent-based zone simulation, 5 counterfactual scenarios, generative latent-space scenario synthesis

**Frontend** — React 18, TypeScript, Vite 6, Tailwind CSS 3.4, Three.js, Framer Motion, Recharts

**Deployment** — Render (FastAPI backend), GitHub Pages (React SPA)

## Features

- **Predictive occupancy forecasting** — 18 engineered features from 15-min time buckets using cyclical encoding, lag windows, rolling statistics, parking-event flux, and anomaly detection
- **Dynamic pricing** — Neural agent learns revenue-maximizing price multipliers; QMIX coordinates multi-zone pricing
- **Blockchain audit trail** — Every parking session and payment recorded on a SHA-256 proof-of-work ledger with smart contracts
- **Micro-slot management** — Per-slot 5-state machine (available, prebooked, reserved, occupied, maintenance) with Bayesian Beta-Binomial availability predictor
- **Digital twin simulation** — Counterfactual what-if scenarios (zone closure, price surge, weather, holidays) with generative scenario synthesis
- **IoT sensor fusion** — Dual-redundant ultrasonic + vision sensors with conservative OR consensus

## Quick Start

```bash
# Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn src.main:app --reload

# Frontend demo
cd demo/app
npm install
npm run dev
```

The demo frontend runs at `http://localhost:5173` and proxies `/api` requests to the backend. When the backend is cold (Render free tier), components gracefully fall back to simulated data via the `useApiWithFallback` pattern.

## Project Structure

```
src/
├── api/            # FastAPI route handlers (14 modules)
├── blockchain/     # PoW ledger, smart contracts, IPFS, pool manager
├── digital_twin/   # Zone simulator, scenario engine, generative model
├── features/       # Feature engineering (18 features, 15-min buckets)
├── iot/            # DualSensorPair, parking events, actuator bridge
├── micro/          # Slot state machine, Bayesian predictor, pricing
├── models/         # RF + XGBoost + RidgeCV ensemble training
├── pipeline/       # PipelineOrchestrator (6-layer session loop)
├── rl/             # NeuralAgent DQN, ParkingControlEnv, QMIX MARL
├── main.py         # FastAPI entry point
├── hybrid_loop.py  # End-to-end 6-layer inference loop
├── constants.py    # Shared thresholds, weights, defaults
└── train.py        # Training entry point

demo/app/           # React SPA frontend
├── src/
│   ├── api/        # API client with fallback data
│   ├── components/ # 13 UI sections (hero, prediction, blockchain, etc.)
│   ├── hooks/      # useApi, useScrollReveal
│   └── utils/      # Formatting, classname utilities
└── vite.config.ts  # Dev proxy to Render backend

data/               # Parking datasets (Birmingham, Melbourne)
whitepaper.pdf      # Technical architecture whitepaper
```

## API Overview

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Backend health check |
| `POST /auth/login` | JWT authentication |
| `GET /api/v1/occupancy` | Current occupancy across lots |
| `GET /api/v1/dashboard` | Aggregated dashboard metrics |
| `GET /api/v1/blockchain/status` | Blockchain ledger state |
| `GET /api/v1/pricing/zones` | Pricing zone configuration |
| `GET /api/v1/micro/slots` | Per-slot availability |
| `POST /api/v1/predict` | Occupancy forecast |
| `POST /api/v1/twin/simulate` | Run a digital twin scenario |
| `POST /api/v1/sessions` | Create parking session |
| `GET /api/v1/system/health` | Subsystem health probe |

## License

MIT
