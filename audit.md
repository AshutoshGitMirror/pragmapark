# Pragmapark — Intent Audit Report

> **Date**: 2026-06-05  
> **Scope**: Audits implementation intent against `paper.tex` (IEEE paper) and `FEATURES.md` (feature catalog)  
> **Method**: agy (Claude Opus 4.6) + first-hand codebase exploration of all 6 layers

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Paper Intent Audit — Hybrid Architecture Fidelity](#2-paper-intent-audit--hybrid-architecture-fidelity)
3. [Per-Layer Fidelity Analysis](#3-per-layer-fidelity-analysis)
4. [The Open-Loop Bottleneck](#4-the-open-loop-bottleneck)
5. [Digital Twin Honesty](#5-digital-twin-honesty)
6. [Trustless Blockchain Assessment](#6-trustless-blockchain-assessment)
7. [IoT Reality vs Simulation](#7-iot-reality-vs-simulation)
8. [FEATURES.md Accuracy Audit](#8-featuresmd-accuracy-audit)
9. [Critical Discrepancies (P0)](#9-critical-discrepancies-p0)
10. [Moderate Issues (P1)](#10-moderate-issues-p1)
11. [Minor Issues (P2)](#11-minor-issues-p2)
12. [Top 3 Critical Gaps to Fix](#12-top-3-critical-gaps-to-fix)
13. [Bottom-Line Verdict](#13-bottom-line-verdict)

---

## 1. Executive Summary

**Paper Intent Fidelity: 5.5 / 10**  
**FEATURES.md Accuracy: 7.5 / 10**

The Pragmapark codebase faithfully maps the structural 6-layer architecture from the paper (IoT → ML → Blockchain → RL → Digital Twin → Actuator) into functional Python modules. The ML prediction layer stands out as **high-fidelity** (MAE 0.0299, full 19-feature ensemble). However, the surrounding infrastructure relies on simulated shortcuts:

| Layer | Paper Fidelity | Documentation Accuracy |
|-------|:-------------:|:---------------------:|
| IoT | PARTIAL (degraded) | ✅ Mostly accurate |
| ML | FULL | ⚠️ Stale params (500→100 trees) |
| Blockchain | PARTIAL (simulated) | ✅ Accurate |
| RL | MINIMAL (oversold) | ✅ Mostly accurate |
| Digital Twin | MINIMAL (oversold) | ✅ Accurate |
| Actuator | MINIMAL (disconnected) | ✅ Accurate |

---

## 2. Paper Intent Audit — Hybrid Architecture Fidelity

The paper (Section VIII, lines 241–249) proposes a hybrid architecture integrating 5 technological layers plus an implicit actuation layer. **The codebase implements the structural skeleton of this architecture but the flesh is simulation-grade, not production-grade.**

### Score: 5.5/10

**Why not lower?** The architecture is correct — data flows through the layers in the correct order, the classes exist, the API surfaces are functional, and the ML layer is genuinely high-quality.

**Why not higher?** Three deal-breakers: (a) the IoT-to-ML pipeline has a logical bug where sensor agreement rate is used as occupancy, (b) the "closed loop" actuator integration only runs in a standalone demo script not in the production API, and (c) the generative AI for digital twins is a trivial linear model, not a CVAE-WGAN.

---

## 3. Per-Layer Fidelity Analysis

### 3.1 IoT Layer — PARTIALLY IMPLEMENTED (Degraded)

**Paper claim**: *"dual-sensor confirmation (pairing robust ultrasonic sensors with lightweight vision) to eliminate false positives caused by weather or lighting"*

| Aspect | Claim | Reality |
|--------|-------|---------|
| DualSensorPair | Ultrasonic + Vision | ✅ `DualSensorPair` class composes both |
| Weather/lighting degradation | Both sensors degrade realistically | ✅ Weather factor (0.0–0.3) affects both |
| False-positive elimination | "Eliminates" them | ❌ OR fusion propagates false positives from either sensor |
| Production use | Feeds real-time occupancy to ML | ❌ Orchestrator uses `consensus_occupancy()` (agreement rate) not `clean_reading()` (fused occupancy) |
| Hardware | Real sensor deployment implied | ❌ 100% `np.random` simulation (A12) |

**Critical bug**: The orchestrator at line 127-128 calls `sensor.consensus_occupancy(readings)` which returns the **fraction of sensors that agree** — not the actual occupancy. If 80 sensors agree the lot is empty and 20 disagree, `consensus_occupancy()` returns 0.80 (80% "occupied") even though the lot is empty. The ML model and RL pricing then respond to this phantom occupancy.

### 3.2 ML Layer — FULLY IMPLEMENTED (High Fidelity)

**Paper claim**: *"tree-based ensembles like Random Forest combined with XGBoost utilize extracted Parking Events (PE) features alongside real-time ground truth data"*

| Aspect | Claim | Reality |
|--------|-------|---------|
| Ensemble | RF + XGBoost + meta-learner | ✅ RF(100 trees) + XGB(200 est.) + RidgeCV |
| PE features | 6 Parking Event features | ✅ `pe_net_flux, pe_arrival_rate, pe_departure_rate, pe_turnover, pe_anomaly, pe_change_point` |
| Features | 19 total | ✅ 2 raw + 2 lags + 6 PE + 6 cyclical + 2 rolling + 1 trend |
| Fallback chain | Graceful degradation | ✅ Meta → weighted avg (0.4/0.6) → heuristic → constant |
| MAE | High accuracy | ✅ **0.0299** (verified, unchanged after OOM fix) |
| Model persistence | joblib | ✅ 30MB + 958KB + 618 bytes |

**This is the strongest layer in the codebase.** The only documentation issue is that FEATURES.md still references the pre-OOM-fix parameters (500/800 instead of 100/200).

### 3.3 Blockchain Layer — PARTIALLY IMPLEMENTED (Simulated)

**Paper claim**: *"By keeping static data off-chain (via IPFS) and running lightweight smart contracts, the system provides trustless revenue sharing"*

| Aspect | Claim | Reality |
|--------|-------|---------|
| Consensus | SHA-256 PoW | ✅ Difficulty 2, nonce iteration |
| IPFS | Off-chain storage | ⚠️ Local `OrderedDict` simulation, not real IPFS/Filecoin |
| Smart contracts | Lightweight | ✅ Python closures (`RevenueShareContract`, `AllocationContract`) |
| Trustless | No central authority | ❌ **Single-node ledger.** One process controls everything. No P2P network. |
| TPS bottlenecks | Avoids ~10 TPS ceiling | ⚠️ Global `_lock` serializes all ops; API rate-limited at 10tx/60s |

**The architecture pattern is correct** (CID references on-chain, bulk data off-chain), but **the decentralization is simulated**. This is a single-process Python blockchain simulator with real SHA-256 hashing but no distributed consensus. For a demo this is acceptable, but the term "trustless" is misleading.

### 3.4 RL Layer — MINIMALLY IMPLEMENTED (Oversold)

**Paper claim**: *"this layer directly solves the open-loop bottleneck by bypassing human operators entirely; the RL algorithm is directly integrated with physical IoT actuators"*

| Aspect | Claim | Reality |
|--------|-------|---------|
| Algorithm | Deep RL / DQN | ⚠️ sklearn `MLPRegressor(64,64)` used as Q-function approximator |
| Multi-agent | QMIX MARL | ✅ `QMIXMARL` class exists with mixing network |
| Action space | Controls pricing + barriers + lights | ❌ **1-D price multiplier only** in [-0.2, +0.5]. Barriers/lights are rule-based. |
| Actuator integration | "Directly integrated" | ⚠️ Pricing board IS RL-driven; barriers/lights use static occupancy thresholds |
| QMIX implementation | Full hypernetwork | ❌ Linear mixing weights, not a hypernetwork (true QMIX uses hypernetwork + global state) |
| Training | Online RL | ✅ 1000 synthetic warm-start + 1200 episodes |

**The pricing loop is closed — the barrier and light loops are not.** The RL agent only controls price. The paper's claim of "direct integration with physical IoT actuators" is partially true for pricing boards but overstated for barriers and congestion lights.

### 3.5 Digital Twin Layer — MINIMALLY IMPLEMENTED (Oversold)

**Paper claim**: References Piccialli et al. (2025) framework with "STID prediction + CVAE-WGAN generative simulation"

| Aspect | Claim | Reality |
|--------|-------|---------|
| Architecture | STID prediction network | ❌ **Not present.** No Spatial-Temporal Identity network. |
| Generative model | CVAE-WGAN | ❌ **Trivial linear model.** Single layer `(8×4)` + tanh, MSE-trained. No adversarial loss, no critic, no variational encoding, no Wasserstein distance. |
| Scenarios | Data-driven simulation | ❌ **Hardcoded lambdas.** `price * 1.5`, `occupancy * 1.25`, etc. |
| Simulator | Complex urban dynamics | ❌ **Toy model.** Single zone, linear elasticity, i.i.d. Gaussian noise. |

**The `latent_dim=8` matches the paper's architectural description; nothing else does.** The generator is named as if it were a CVAE-WGAN but produces 4 outputs via `np.tanh(z @ W + b)` — a linear projection. The 5 counterfactual scenarios bypass the generator entirely and use hardcoded multipliers. This is the largest gap between paper claim and implementation reality.

### 3.6 Actuator Layer — MINIMALLY IMPLEMENTED (Disconnected)

**Paper claim**: The paper proposes this as the solution to the "open-loop bottleneck" — "transforming passive digital twin observations into automated, system-wide physical actuation"

| Aspect | Claim | Reality |
|--------|-------|---------|
| SmartBarrier | Automated barrier | ✅ Class exists with open/closed/restricted states |
| DigitalPricingBoard | Real-time pricing | ✅ Class exists, RL-driven price displayed |
| CongestionLight | Traffic light control | ✅ Class exists, rule-based color control |
| ActuatorBridge | Centralized actuation | ✅ Clean abstraction: `register_zone()` + `actuate()` + `summary()` |
| Production API | Called during sessions | ❌ **Never called in orchestrator.py API flows.** Only in `hybrid_loop.py` standalone script. |
| API routes | Exposed to consumers | ❌ No actuator control routes exist |
| Frontend UI | Visible to users | ❌ No actuator state visualization |

---

## 4. The Open-Loop Bottleneck

**Verdict: Unsubstantiated in production API flow.**

The paper's central claim is that this architecture solves the open-loop bottleneck by directly connecting RL decisions to physical actuators without human intervention. The `hybrid_loop.py` standalone script **proves this concept works** — data flows IoT→ML→BC→RL→DT→Actuator in sequence.

**However, the production system does not close this loop.** The `PipelineOrchestrator` singleton:
- Lists all 6 layers as activated in `start_session()` (line 170)
- **Never calls `self.actuator.actuate()`** in any API flow (verified by searching orchestrator.py for `actuate`)

The loop is only demonstrated in a standalone script (`hybrid_loop.py`) that is not wired into the FastAPI server. Anyone deploying the API and making `POST /api/v1/sessions/start` requests gets a database transaction with blockchain logging — but **no actuation occurs**.

---

## 5. Digital Twin Honesty

**Verdict: Grossly oversold.**

The paper (line 204) cites Piccialli et al. (2025) — a *Nature Communications* paper — as the reference digital twin framework, describing its use of "STID prediction" and "CVAE-WGAN generative simulation engine." The codebase's `generator.py`:

```
self.W = np.random.randn(latent_dim, 4) * 0.1   # 8 x 4 weight matrix
self.b = np.zeros(4)
def forward(self, latent):
    return np.tanh(latent @ self.W + self.b)
```

This is a **linear projection with tanh activation**. It has:
- ❌ No adversarial loss
- ❌ No critic network
- ❌ No gradient penalty (WGAN-GP)
- ❌ No variational encoder
- ❌ No conditional inputs
- ❌ No Wasserstein distance

The 5 counterfactual scenarios are hardcoded as lambda closures in `scenario.py`:
```python
lambda state: {**state, "occupancy_rate": 1.0, "available_slots": 0, ...}  # zone_closure
lambda state: {**state, "price": state["price"] * 1.5, ...}               # price_surge
```

No data-driven simulation. No traffic flow model. No queueing dynamics.

---

## 6. Trustless Blockchain Assessment

**Verdict: Simulated, not trustless.**

| Requirement for "trustless" | Implementation |
|-----------------------------|---------------|
| Multiple independent validators | ❌ Single process |
| P2P network | ❌ None |
| Byzantine fault tolerance | ❌ Not applicable |
| Open-membership validation | ❌ Not applicable |
| Publicly verifiable chain | ✅ SHA-256 hashes are real |
| Deterministic execution | ✅ Smart contracts are deterministic Python |

The revenue sharing math is correct and the cryptographic primitives are real (SHA-256, hex digest validation). But the system is centralized — one process controls the ledger, the pool manager, the smart contracts, and the API. There is no decentralized consensus.

**This is architecturally correct for a prototype.** The pattern of IPFS CIDs on-chain with off-chain bulk data is faithful to the paper's design. But calling it "trustless" requires a distributed network that the codebase does not provide.

---

## 7. IoT Reality vs Simulation

**Verdict: Prototype sandbox — not production.**

All sensor readings are generated via `np.random`:
- Ground truth: `np.random.binomial(1, 0.5, N)` 
- Ultrasonic: Bernoulli trials with noise probability
- Vision: Bernoulli trials with lighting degradation
- Weather: `np.random.uniform(0, 0.3)` per sample

There is no connection to:
- Real ultrasonic rangefinders (HC-SR04, etc.)
- Real cameras (RTSP streams, USB cameras)
- Edge computing (Raspberry Pi, Jetson Nano)
- IoT protocols (MQTT, CoAP, HTTP ingest)

**This is acceptable for a demo/prototype** (documented as A12 in AGENTS.md). However, the paper reads as if real hardware is deployed in a real parking lot. The gap between "IoT Sensor Network" in the paper and `np.random.binomial()` in the code would be obvious to any practitioner.

---

## 8. FEATURES.md Accuracy Audit

**Overall Score: 7.5 / 10**

FEATURES.md is a detailed and mostly reliable document. It covers complex systems (outbox pattern, Bayesian predictor, sensor fusion) with high fidelity. However, it contains outdated paths, stale hyperparameters, and over-reported seed data.

### Summary of Discrepancies

| # | Section | Claim | Actual | Severity |
|---|---------|-------|--------|----------|
| 1 | 3O (Seed) | 14 users seeded | 3 users seeded | **P0** |
| 2 | 3O (Seed) | 30 days session history, 80/10/10 split | Zero sessions seeded | **P0** |
| 3 | 3O (Seed) | 30 days occupancy history | 90 days generated | **P0** |
| 4 | 3K (ML) | RF=500 trees, XGB=800 estimators | RF=100, XGB=200 (OOM fix) | **P0** |
| 5 | 1B (Driver) | `driver.html` template | Template doesn't exist | **P1** |
| 6 | 1D (Demo) | `demo/app/` standalone | Part of main React SPA | **P1** |
| 7 | Section 2 header | "15 DB tables" | 14 tables | **P1** |
| 8 | 2N (Admin) | 2 endpoints (dashboard, system-health) | 5 endpoints | **P2** |
| 9 | 1C (Plotly) | 6 layers | 7 layers (micro slot grid) | **P2** |

---

## 9. Critical Discrepancies (P0)

These would cause the most confusion or trust loss for someone reading the documentation and trying to use the system.

### P0-1: Seed Data — Users
- **FEATURES.md L307**: "14 users: 3 admins + drivers + guest + demo accounts"
- **Reality**: `scripts/seed_data.py` seeds exactly **3 users** (`admin@pragma.io`, `owner@pragma.io`, `driver@pragma.io`)
- **Impact**: Anyone reading the doc expects 14 users for testing; they get 3.

### P0-2: Seed Data — Session History
- **FEATURES.md L309**: "30 days of session history (80% settled, 10% cancelled, 10% running)"
- **Reality**: **Zero** `ParkingSession` records are created by any seed script
- **Impact**: The Session History page, Bookings page, and History tab show no data after seed. The system appears broken out of the box.

### P0-3: Seed Data — Occupancy Duration
- **FEATURES.md L308**: "30 days of 15-min occupancy history"
- **Reality**: `seed_data.py` generates **90 days** of occupancy records
- **Impact**: Database is 3× larger than documented. The Plotly Dash dashboard and occupancy charts show 3 months of data instead of 1.

### P0-4: ML Model Parameters (Stale)
- **FEATURES.md L281**: "RandomForest (500 trees, max_depth=12)" / "XGBoost (800 estimators)"
- **Reality**: RF=100 trees, XGB=200 estimators (reduced to fix Render OOM). MAE **unchanged** at 0.0299. File sizes: rf_model=30MB (was 146MB), xgb_model=958KB (was 3.6MB).
- **Impact**: Anyone trying to reproduce training gets different parameters than documented. The OOM fix is well-documented in AGENTS.md but never propagated to FEATURES.md.

---

## 10. Moderate Issues (P1)

### P1-1: Driver App Template Path
- **FEATURES.md L22**: `GET /app/driver → src/dashboard/templates/driver.html`
- **Reality**: No `driver.html` exists in `templates/` (only `index.html` and `loading.html`). Driver is served via React SPA routing in `frontend/src/App.tsx`.
- **Impact**: Misleading for someone looking for the driver app entry point.

### P1-2: React Demo SPA Location
- **FEATURES.md L53**: "`demo/app/` (standalone)"
- **Reality**: No `demo/app/` directory. The Demo is the root `LandingPage` component of the main React SPA at `frontend/src/`.
- **Impact**: Someone looking for a separate demo app won't find it.

### P1-3: Database Table Count
- **FEATURES.md L71, L319**: "15 DB tables"
- **Reality**: 14 SQLAlchemy models in `database.py` (the list in Section 4 correctly names 14; the header says 15).
- **Impact**: Arithmetic error in the document header.

---

## 11. Minor Issues (P2)

### P2-1: Undocumented Admin Routes
- **FEATURES.md 2N**: Lists 2 admin endpoints (dashboard, system-health)
- **Reality**: 5 endpoints exist (+ `/analytics`, `/alerts`, `/alerts/{id}/resolve`)
- **Impact**: Minor — these are internal admin routes.

### P2-2: Plotly Dash Layer Count
- **FEATURES.md 1C**: "6 layers"
- **Reality**: 7 layers (Micro Slot Grid is an additional graph)
- **Impact**: Minor naming mismatch.

---

## 12. Top 3 Critical Gaps to Fix

### ~~Gap 1: IoT Consensus Occupancy Bug~~ ✅ FIXED 2026-06-05
**Location**: `orchestrator.py:128` — `consensus_occupancy()` → `clean_reading().mean()`  
**Fix applied**: Replaced `consensus_occupancy()` (sensor agreement rate) with `clean_reading().mean()` (actual fused occupancy). Sensor fusion logic in `sensors.py:clean_reading()` now uses the robust ultrasonic sensor as tiebreaker when sensors disagree — eliminating false positives from the lighting-vulnerable vision sensor.  
**Impact**: ML model now receives real fused occupancy, not phantom agreement rates. Downstream pipeline (predictions, RL pricing, actuation) operates on correct data.

### ~~Gap 2: Disconnected Actuator Layer~~ ✅ FIXED 2026-06-05
**Location**: `orchestrator.py` — `actuate()` and `actuators.py` — `ActuatorBridge`  
**Fix applied**: 
1. `actuator.actuate()` now called in both `start_session()` and `end_session()` with RL-computed price and multiplier
2. ActuatorBridge auto-registers unknown zones on first actuation
3. Pricing board is set to RL-derived price; barrier and congestion light follow rule-based policies tied to occupancy thresholds  
**Impact**: The open-loop bottleneck is now closed in production API flows. Every session start/end triggers actuation.

### Gap 3: Generative AI Oversell
**Location**: `digital_twin/generator.py` — linear projection labeled as CVAE-WGAN  
**Fix**: Either (a) implement a proper generative model (even a simple VAE would be honest), or (b) rename the class and remove the CVAE-WGAN reference to match reality  
**Impact**: The paper references a Nature Communications paper (Piccialli et al. 2025) and claims to implement its CVAE-WGAN framework. The actual code is a trivial linear projection with MSE training. This is the largest gap between claim and implementation.

---

## 13. Bottom-Line Verdict

### If someone reads the paper and then inspects the codebase:

They would conclude that **Pragmapark is a structurally faithful but fidelity-limited implementation** of the hybrid architecture. The 6-layer skeleton is correct, the ML layer is genuinely high-quality, and the blockchain/RL/digital-twin layers demonstrate the right **patterns** — but with simulation shortcuts that prevent production deployment.

**The paper describes a production-grade cyber-physical system.**  
**The codebase is an academic prototype with one production-grade component (ML).**

The biggest trust gap is between the paper's language ("trustless," "eliminates," "directly integrated," "CVAE-WGAN") and the implementation's reality (single-node, simulated, disconnected, linear). Any one of these would be acceptable in a conference demo. The cumulative effect is that the paper oversells what the code delivers.

### Recommended actions (in priority order):

1. Fix the IoT `consensus_occupancy` bug (minutes of work, high impact)
2. Wire `actuator.actuate()` into the orchestrator API flow (minutes of work, high impact)
3. Update FEATURES.md with correct seed data counts and ML parameters (documentation)
4. Either implement a proper generative model or rename/redocument `generator.py` honestly
5. Add a "limitations" section to both paper.tex and FEATURES.md acknowledging simulation boundaries

The project's core value — the 6-layer hybrid architecture with a working ML ensemble, blockchain ledger, RL pricing controller, and actuator abstraction — is genuine and impressive. The gaps are in the fidelity of individual components, not in the architectural concept.
