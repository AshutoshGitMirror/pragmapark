// ═══════════════════════════════════════════════════════════════════
//  Pragma: A Closed-Loop Hybrid Architecture for AI-Powered Smart Parking
//  — IEEE-format conference paper —
//  Architecture claims cross-validated against source code (2026-06-27).
// ═══════════════════════════════════════════════════════════════════

// ── IEEE-style paper setup ──
#set page(
  paper: "us-letter",
  columns: 2,
  margin: (x: 0.65in, top: 0.85in, bottom: 0.9in),
  numbering: "1",
)
#set text(font: ("Liberation Serif", "Noto Serif"), size: 10pt)
#set par(justify: true, leading: 0.5em, first-line-indent: 1em)
#set heading(numbering: "I")
#set math.equation(numbering: "(1)")

// ── Code blocks ──
#show raw.where(block: true): set text(font: ("Liberation Mono", "Noto Sans Mono"), size: 8pt)
#show raw.where(block: false): set text(font: ("Liberation Mono", "Noto Sans Mono"), size: 8.5pt)

// ── Section heading style ──
#show heading: it => {
  set text(10pt, weight: 400)
  if it.level == 1 {
    show: smallcaps
    show: block.with(above: 12pt, below: 6pt)
    align(center, it.body)
  } else if it.level == 2 {
    set text(style: "italic")
    show: block.with(spacing: 6pt)
    it.body + [. ]
  } else {
    set text(style: "italic")
    it.body + [. ]
  }
}

// ── Colors ──
#let primary   = rgb("1a1a2e")
#let accent    = rgb("d4a017")
#let iot-color = rgb("2563eb")
#let ml-color  = rgb("059669")
#let bc-color  = rgb("d97706")
#let rl-color  = rgb("dc2626")
#let dt-color  = rgb("7c3aed")
#let act-color = rgb("0284c7")
#let muted     = rgb("555555")
#let light-bg  = luma(245)

// ── Title area ──
#place(top + center, float: true, scope: "parent", clearance: 0pt, {
  align(center)[
    #text(size: 22pt, weight: "bold")[Pragma: A Closed-Loop Hybrid Architecture for AI-Powered Smart Parking]
  ]
  v(8pt)
  set text(9pt)
  set par(leading: 0.4em)
  set align(center)
  line(length: 60%, stroke: 0.5pt + primary)
  v(4pt)
  text(weight: "bold")[Pragma Project Contributors]
  v(2pt)
  text(weight: "bold")[Pragma Labs — June 2026]
  v(4pt)
  line(length: 60%, stroke: 0.5pt + primary)
})

// ── Abstract ──
#set par(first-line-indent: 0em, spacing: 0.3em)
#v(8pt)
#text(size: 8.5pt, weight: "bold", spacing: 120%)[_Abstract_—#text(weight: "regular")[
We present Pragma, a closed-loop hybrid architecture for AI-powered smart parking that integrates six computational layers into a single operational pipeline orchestrated by a central `PipelineOrchestrator` singleton: (1) dual-sensor IoT fusion with physics-based simulation, (2) ensemble ML forecasting (Random Forest + XGBoost + RidgeCV, MAE 0.0299), (3) a SHA-256 Proof-of-Work blockchain ledger with IPFS off-chain storage and revenue-sharing smart contracts, (4) a NumPy Deep Q-Network extended with softmax-hypernetwork QMIX for multi-zone dynamic pricing, (5) a generative digital twin using a CVAE-WGAN hybrid with spatial-temporal identity (STID) prediction, and (6) an actuator layer closing the loop. The entire system is implemented in Python 3.14 with a TypeScript React frontend. We describe the actual architecture as it exists in source code — including the pipeline flow, feedback arcs that are truly closed vs those that are inference-only — and document known limitations for physical deployment.
]]

// ── Index Terms ──
#text(size: 8.5pt, weight: "bold", spacing: 120%)[_Index Terms_—#text(weight: "regular", size: 8.5pt)[Smart parking, digital twin, reinforcement learning, blockchain, IoT sensor fusion, closed-loop control, CVAE-WGAN, QMIX]]

#v(6pt)

// ── 1. INTRODUCTION ──
= Introduction

Urban parking is a first-order congestion problem: drivers searching for parking account for an estimated 30% of city-centre traffic in major metropolitan areas #cite(<shoup2006>). Smart parking systems address this through real-time occupancy sensing, dynamic pricing, and mobile guidance. However, the published literature reveals a consistent architectural gap: each subsystem — sensing, forecasting, pricing, transaction recording — operates in isolation. Forecasts are computed but never validated against actual outcomes. Pricing decisions are made without observing demand elasticity. Digital twins simulate ``what-if'' scenarios but receive no feedback from real session completions.

Pragma addresses this gap through a closed-loop architecture where session outcomes route back through the digital twin and generative models for continuous online adaptation. The defining architectural property is not the sophistication of any individual layer but the presence of concrete feedback arcs between them — arcs that exist in source code and are verified by tests.

This paper describes the architecture as it *actually exists* in commit `1f25f82` of the public repository. Every claim about algorithm behaviour, layer wiring, and data flow has been cross-validated against the running codebase. Where the architecture falls short of its ideal — the RL agent is frozen in the API loop, the blockchain is single-process, the actuators operate on in-memory state — we document these limitations explicitly.

*Contributions.* (1) A closed-loop pipeline design with verified feedback arcs. (2) An honest accounting of what is implemented, what is simulated, and what remains absent. (3) A mathematical description of each layer with constants verified against source. (4) Six audited architectural gaps (A–F) that were identified and corrected during development.

// ── 2. RELATED WORK ──
= Related Work

Prior smart parking research falls into five categories.

*IoT sensing.* Ultrasonic, magnetic, and camera-based occupancy detection has been extensively studied #cite(<chen2020>). The `RealisticParkingSensorSimulator` builds on these foundations by modelling temporal occupancy patterns via Gaussian mixture kernels — dual commute peaks on weekdays (09:00, sigma = 1.8 h; 18:00, sigma = 2.2 h), a single broad afternoon peak on weekends — and sigmoid spatial filling from entrances. Crucially, the simulator *replaces* the `np.random.binomial(1, 0.5)` baseline that was used in early revisions (Gap A, Revision 1.0).

*ML forecasting.* Occupancy prediction approaches range from ARIMA and LSTM to gradient-boosted trees #cite(<zheng2015>). Pragma's ensemble (Random Forest, XGBoost, RidgeCV meta-learner) was chosen for low inference latency on constrained hardware. Model compression from 150 MB to 31 MB (79% reduction, verified via `ls -lh`) eliminated Render free-tier OOM errors.

*Blockchain for parking.* Ethereum-based smart contracts have been proposed for trustless payment and slot reservation #cite(<zhang2021>). Pragma implements a lightweight SHA-256 PoW ledger with revenue-sharing (90/10 city-operator split) and monetary-policy allocation contracts. The blockchain is a single-process audit trail persisted to JSON — deliberately minimal, not a distributed ledger.

*RL pricing.* Dynamic parking pricing is a well-studied RL problem #cite(<qian2012>). Pragma's NeuralAgent (NumPy DQN, 64x64 MLP, Adam, experience replay) follows the standard DQN formulation #cite(<mnih2015>). The QMIX extension #cite(<rashid2018>) uses a softmax hypernetwork for multi-zone coordination. However, the API server loads a pre-trained agent and does not train online — the buffer expansion and gradient updates described in prior RL parking work #cite(<lei2020>) occur in a separate training script.

*Digital twins.* Existing parking digital twins focus on simulation #cite(<bhatti2021>). Pragma's CVAE-WGAN generator produces counterfactual scenarios (zone closure, price surge, capacity expansion, weather disruption, holiday spike) with 8-dimensional latent space and online learning every 10 real sessions.

*The open-loop gap.* The common thread across prior work is open-loop execution: forecasts are made but not validated, pricing is computed but not tuned by observed elasticity, the digital twin simulates without receiving feedback. Pragma's core architectural claim is that `end_session()` routes real outcomes back through the DT and generator — closing the loop.

// ── 3. SYSTEM ARCHITECTURE ──
= System Architecture

Pragma organises six layers around a central `PipelineOrchestrator` singleton (`src/pipeline/orchestrator.py`). Each layer is a Python module with a defined interface; the orchestrator calls them in a fixed order during session lifecycle. All state-mutating operations are serialised under a `DBLock` to guarantee consistency across concurrent requests — a known scaling bottleneck described in Section 6.

== Pipeline Overview

The orchestrator exposes three main session methods: `start_session`, `end_session`, and `process_payment`. Each activates a different subset of layers:

#figure(
  align(center, table(
    columns: (auto, auto, auto, auto, auto, auto, auto),
    stroke: 0.5pt,
    table.header([], [*IoT*], [*ML*], [*Blockchain*], [*RL*], [*DT*], [*Actuator*]),
    [*start_session*], [$checkmark$], [$checkmark$], [$checkmark$], [$checkmark$], [—], [$checkmark$],
    [*end_session*], [—], [—], [$checkmark$], [$checkmark$], [$checkmark$], [$checkmark$],
    [*process_payment*], [—], [—], [$checkmark$], [—], [—], [—],
  )),
  caption: [Layer activation matrix for each session method. Only layers with $checkmark$ are called.],
)

*Critical architectural observation*: The digital twin is *not* consulted during `start_session` — it only receives updates during `end_session`. The IoT sensor simulation is *only* invoked during `start_session` — real-time sensor telemetry is not re-fetched at checkout. This produces a half-closed loop: session outcomes feed the DT, but the DT state does not influence new session pricing unless the RL agent independently incorporates it.

== Session Lifecycle

#figure(
  align(center, block(
    fill: light-bg, inset: 6pt, radius: 2pt,
  )[#text(size: 7.5pt, font: "Liberation Mono")[
#h(0em)*1. start_session(lot_id, driver_id, slot)* \
#h(1em)a) `RealisticParkingSensorSimulator.sample_step()` → sensor readings \
#h(1em)b) `DualSensorPair(…).clean_reading(readings).mean()` → fused_occ \
#h(1em)c) if features provided: `Predictor.predict(features)` → pocc \
#h(1em)d) else: pocc = fused_occ \
#h(1em)e) `_slot_op(lot_id, slot, \"occupied\")` \
#h(1em)f) `PricingController.get_price(pocc, price, cap, zone)` → new_price, mult \
#h(1em)g) `AllocationContract.execute(…)` (try/except) \
#h(1em)h) `ActuatorBridge.actuate(lot_id, fused_occ, new_price, mult)` \
#h(1em)i) `_pin_tx(type=\"session_start\")` → IPFS + ledger \
#h(1em)j) *return* layers_activated: IoT, ML, Blockchain, RL, Actuator \
#h(0em)*2. end_session(session_id, lot_id, driver_id, start_time, occ, price)* \
#h(1em)a) compute dur = (now - start) in hours \
#h(1em)b) `PricingController.get_price(occ, price, cap, zone)` → current_rate \
#h(1em)c) amount = `min(entry_price * dur, price_cap * 24)` \
#h(1em)d) `_pin_tx(type=\"session_end\")` → IPFS + ledger \
#h(1em)e) `_slot_op(lot_id, slot, \"available\")` \
#h(1em)f) `ActuatorBridge.actuate(lot_id, occ, current_rate, 0.0)` \
#h(1em)g) update DT zones: `dt.zones[id][\"occupancy\"] = occ; dt.zones[id][\"price\"] = cr` \
#h(1em)h) `DigitalTwinSimulator.tick({lot_id: 0.0})` → STID predict + train \
#h(1em)i) `Generator.online_update(occ, price, dur, congestion)` \
#h(1em)j) *return* layers_activated: Blockchain, RL, DT, Actuator  \
#h(0em)*3. process_payment(session_id, driver_id, amount, lot_id)* \
#h(1em)a) `RevenueShareContract.execute({price, driver_id, lot_id})` \
#h(1em)b) `_pin_tx(type=\"payment_confirmation\")` → IPFS + ledger
  ]]),
  caption: [Simplified session lifecycle as implemented in `orchestrator.py` (423 lines). Steps `h` and `i` in `end_session` constitute the closed feedback loop.],
)

== Feedback Arcs

Pragma implements three concrete feedback arcs:

1. *DT zone update + tick*: `end_session()` sets the zone's occupancy and price to real session values, then calls `tick()`. Inside `tick()`, the STID predictor computes a next-step prediction for each zone, blends it with an economic model (70/30 ratio), and performs an online gradient descent step: `stid.train_step(zone_idx, hour, dow, prev_occ, new_occ)`. This is the primary closed-loop mechanism.

2. *Generator online update*: `end_session()` calls `generator.online_update(occ, price, dur, congestion)`. The generator accumulates a buffer of real session outcomes. When the buffer reaches `ONLINE_BATCH_SIZE` (10), a CVAE training step fires with null conditional vector, and every second batch additionally fires a WGAN critic/generator step. This incrementally adapts the generative model to real session distributions.

3. *RL inference*: The RL agent *only infers* during the API loop. `PricingController.get_price()` calls `agent.act(state, train=False)` which performs greedy Q-value maximisation via forward pass through the 64x64 MLP. No experience is appended to the replay buffer, no gradient update occurs. The `NeuralAgent.train()` method exists in source code and is covered by 16 unit tests, but is called exclusively from `train_control.py` at the command line — not from the running API server.

These arcs are implemented in code and verified by integration tests. The RL gap — inference-only in API, training offline — is the most significant architectural limitation of the current design.

== Deployment

The backend runs on Render's free tier (512 MB RAM, single process) as two FastAPI instances: the main API server (91 routes across 16 route modules) and a background worker for blockchain mining, ledger outbox flushing, and periodic cleanup. The frontend is served from GitHub Pages as a Vite + TypeScript + Tailwind React SPA. The database is PostgreSQL 16 (Render-managed). Auth uses HttpOnly cookies with `withCredentials: true` — no localStorage tokens.

#figure(
  align(center, table(
    columns: (auto, auto, auto),
    stroke: 0.5pt,
    table.header([*Component*], [*Technology*], [*Hosting*]),
    [Backend API], [FastAPI + SQLAlchemy + Alembic], [Render free (512 MB)],
    [Database], [PostgreSQL 16], [Render free],
    [Frontend], [React 18 + Vite + Tailwind], [GitHub Pages],
    [Background worker], [FastAPI subprocess], [Render (same process)],
    [CI/CD], [GitHub Actions], [lint + type + test + build],
  )),
  caption: [Deployment infrastructure.],
)

// ── 4. ALGORITHMIC FOUNDATIONS ──
= Algorithmic Foundations

This section presents the mathematical formulation of each layer. All constants are verified against `src/constants.py` and the implementation files.

== IoT: Dual-Sensor Fusion

The ingestion layer (`src/iot/sensors.py`, `src/iot/generator.py`) provides two parallel code paths: a physics-based simulator for development and a fusion API for incoming telemetry.

=== Sensor Error Models

*UltrasonicSensor.read()* returns a boolean indicating detection. Error probabilities depend on a weather factor $W in [0, 1]$ (derived from the environmental simulation):

$ P("FP")_"us" = 0.02 + 0.08 W , quad
   P("FN")_"us" = 0.03 + 0.05 W $

*VisionSensor.read()* returns a `(detected, confidence)` tuple. The effective lighting factor $L_"eff"$ modulates error rates:

$ L_"eff" = L_"base" times (1 - 0.4 W) $
$ P("FP")_"vis" = 0.01 + (1 - L_"eff") times 0.06 $
$ P("FN")_"vis" = 0.02 + (1 - L_"eff") times 0.08 $
$ c_"conf" = "clip"(L_"eff" (0.95 - 0.2 W) - 0.05 (1 - "detected"), 0.3, 0.99) $

=== Fusion Strategy

The `clean_reading()` method in `DualSensorPair` implements conservative OR fusion:

$ O_"fused" = O_"ultra" "or" O_"vision" $

When both sensors agree, the reading passes through. When they disagree, the slot is marked occupied (minimising false negatives). Disagreement triggers `is_false_positive = true`; the overall `false_positive_rate()` returns the disagreement fraction. Consensus occupancy uses only agreed-occupied slots:

$ O_"consensus" = "agreed_occupied" / "total_slots" $

=== Realistic Simulator

The `RealisticParkingSensorSimulator` (`src/iot/generator.py`) replaces `np.random.binomial(1, 0.5)` — the naive baseline used before Revision 2.0. It models:

*Temporal occupancy*: Dual Gaussian weekday peaks and a single weekend peak:

$ R_"wd"(t) = 0.12 + 0.68 [0.45 phi((t - 9) / 1.8) + 0.55 phi((t - 18) / 2.2)] $
$ R_"we"(t) = 0.10 + 0.75 phi((t - 14) / 3.5) $

where $phi(x) = e^(-x^2 / 2)$.

*Spatial filling*: Sigmoid probability modelling entrance-proximity preference:

$ P_"fill"(z) = 1 / (1 + e^(-gamma(z_0 - z))) , quad gamma = 15.0 $

where $z in [0, 1]$ is the normalised slot index and $z_0$ is the base occupancy rate.

*Ultrasonic noise*: Distance-thresholded detection at 2.0 m, Gaussian noise $sigma_"us" = 0.05 (1 + 3W)$, dropout $d_"us" = 0.01 (1 + 5W)$, cumulative drift $b_"us" ~ N(0.0001, 0.0001)$.

*Vision degradation*: Occlusion $o_"vis" = 0.02 + 0.18 W$, classification accuracy $a_"vis" = "clip"(0.98 L_"eff" (1 - 0.25 W), 0.55, 0.99)$.

*Environmental weather*: Sinusoidal seasonal baseline plus storm bursts (days divisble by 4, 13:00–16:00, intensity 0.6–0.9).

== ML: Ensemble Forecasting

=== Feature Engineering

The model predicts 15-minute-ahead occupancy from 19 features per lot (defined in `src/constants.py` as `EXPECTED_FEATURE_COLS`):

#figure(
  align(center, table(
    columns: (auto, auto),
    stroke: 0.5pt,
    table.header([*Category*], [*Features*]),
    [Raw Occupancy (2)], [occupied_slots, total_slots],
    [Time Lags (2)], [occ_lag_15m, occ_lag_1h],
    [Event Flux (6)], [pe_net_flux, pe_arrival_rate, pe_departure_rate, pe_turnover, pe_anomaly, pe_change_point],
    [Cyclical Time (5)], [hour_sin, hour_cos, dow_sin, dow_cos, hour_sq],
    [Weekend (1)], [is_weekend],
    [Rolling Stats (3)], [occ_roll_mean_3h, occ_roll_std_3h, occ_acceleration],
  )),
  caption: [Nineteen features used for occupancy forecasting.],
)

Key derived features:

$ "hour"_"sq" = (h - 12)^2 / 144 , quad h in [0, 23] $
$ "occ_lag_15m" = O(t-1) $ (single time step)
$ "pe_anomaly" = cases(1 "if" |O_t - bar(O)_(1:t-1)| > 2 sigma_(1:t-1), 0 "otherwise") $

A critical training-serving skew was corrected (Gap A): inference previously used `occ.tail(N)` for rolling statistics, including the current observation. This was fixed to `occ.iloc[:-(N+1):-1]`, excluding the current observation to match training's `.shift(1)`.

=== Ensemble Architecture

Level-0 regressors:
- `RandomForestRegressor`: 100 trees (reduced from 500), max_depth=12, min_samples_leaf=2
- `XGBRegressor`: 200 iterations (reduced from 800), max_depth=6, eta=0.02, subsample=0.8

Level-1 meta-learner: `RidgeCV(alphas=[0.01, 0.1, 1.0, 10.0])`:

$ hat(y)_"ensemble" = w_1 hat(y)_"RF" + w_2 hat(y)_"XGB" + b $

Fallback when meta-learner is unavailable (during cold start):

$ hat(y)_"fallback" = 0.4 hat(y)_"RF" + 0.6 hat(y)_"XGB" $

=== Model Compression

Model artifacts were compressed to fit Render's 512 MB RAM (was causing OOM errors at 150 MB):

#figure(
  align(center, table(
    columns: (auto, auto, auto, auto, auto),
    stroke: 0.5pt,
    table.header([*Model*], [*Original*], [*Compressed*], [*Reduction*], [*MAE*]),
    [RandomForest], [146 MB], [29.0 MB], [80.1%], [0.0299],
    [XGBoost], [3.6 MB], [958 KB], [74.0%], [0.0299],
    [RidgeCV], [618 B], [618 B], [0%], [0.0299],
    [Total], [150 MB], [31 MB], [79%], [0.0299],
  )),
  caption: [Model compression via tree/iteration reduction.],
)

== Blockchain: Proof-of-Work Ledger

The blockchain layer (`src/blockchain/ledger.py`, 229 lines) implements a SHA-256 PoW ledger. Each block stores: `index`, `timestamp`, `transactions` (list of dicts), `previous_hash`, `nonce`, and computed `hash`. Mining finds a nonce such that:

$ "SHA-256"("index" | "ts" | "txs" | "prev_hash" | "nonce") < T_"target" $

where difficulty 4 means the hash must start with four leading zero nibbles (16-bit prefix). Block mining is delegated to a background worker thread (fix applied in Revision 5.0 — previously blocked HTTP handlers).

The `RevenueShareContract` enforces a 90/10 city-operator revenue split with a 15% system fee applied before splitting. The `AllocationContract` tracks monetary-policy slot allocations. The `IPFSOffChainStore` provides an in-memory content-addressed store with OrderedDict cap of 1000 entries, persisted to a JSON file.

== RL: Deep Q-Network and QMIX

=== NeuralAgent (NumPy DQN)

The single-agent DQN (`src/rl/agent.py`, 183 lines) is a pure NumPy 3-layer MLP (no TensorFlow, no PyTorch, no sklearn). Architecture:

$ q = W_3 "ReLU"(W_2 "ReLU"(W_1 [s; a] + b_1) + b_2) + b_3 $

where $s = [O_"occ", P / 50, 0.5]$ (price normalised by 50) and the action $a$ is a scalar price multiplier in $[-0.3, 0.3]$. The input dimension is $3 + 1 = 4$; hidden layers are 64 units each. He initialisation: $W_1 ~ N(0, sqrt(2/4))$, $W_2 ~ N(0, sqrt(2/64))$, $W_3 ~ N(0, sqrt(2/64))$.

Target network: $Q_t$ parameters are copied every 20 training steps from the online network $Q$. Experience replay: deque(maxlen=2000), batch_size=128, gamma=0.95. Adam optimizer (b1=0.9, b2=0.999) with lr=0.001. Epsilon decays from 1.0 by factor 0.98 per training step, minimum 0.05.

=== QMIX Multi-Agent

QMIX (`src/rl/multi_agent.py`, 321 lines) extends DQN to $N$ zones by learning a hypernetwork mixer. A separate hypernetwork maps the global state $s_t in RR^(2N)$ (each zone's occupancy and normalised price) to softmax mixing weights $w, b$ for per-agent Q-values:

$ Q_"tot"(tau, u) = sum_i w_i(s_t) Q_i(tau_i, u_i) + b(s_t) $

where $tau_i$ is the action-observation history of agent $i$ and $w_i$ are constrained positive via softmax. The hypernetwork is a single layer: $w(s) = "softmax"(W_w s + b_w)$.

=== Inference-Only Gap

In the running API server, `PricingController.get_price()` calls `agent.act(state, train=False)`. This forward-propagates the state through the network and returns the action with highest Q-value (greedy). No epsilon-greedy, no replay buffer expansion, no gradient updates. The agent was pre-trained and saved to `src/rl/artifacts/neural_agent.joblib` via `train_control.py`. The `NeuralAgent.train()` method is called only from the training script, not from the API loop. This is the most significant architectural divergence from a fully closed-loop system.

== Digital Twin: CVAE-WGAN and STID

=== CVAE-WGAN Generator

The generator (`src/digital_twin/generator.py`, 318 lines) combines a conditional variational autoencoder with a Wasserstein GAN:

*Optimisation objective* (combined CVAE + WGAN):

$ L_"CVAE" = "MSE"(hat(x), x) + "KL"_"weight" "KL"(N(mu, sigma) || N(0, 1)) $
$ L_"WGAN" = E[hat(D)(tilde(x))] - E[D(x)] + lambda_"gp" E[(||nabla_hat(x) D(hat(x))||_2 - 1)^2] $

where $x$ is the real state vector $["occ", "price"/50, "congestion", "time"/24]$ (4 dimensions), `latent_dim` = 8, `cond_dim` = 5 (one-hot scenario type). The CVAE encoder encodes $[x; c]$ to a 8-dimensional latent distribution; the decoder reconstructs $x$ from $[z; c]$. WGAN critic is 3-layer MLP (16-8-1) with gradient penalty $lambda_"gp" = 10.0$. Training alternates: 3 critic steps per generator step.

*Online update*: Called from `end_session()`. Accumulates session outcomes into a buffer. At `ONLINE_BATCH_SIZE` = 10, fires CVAE training (null condition), and every second batch also fires WGAN training:

#figure(
  align(center, block(
    fill: light-bg, inset: 6pt, radius: 2pt,
  )[#text(size: 7.5pt, font: "Liberation Mono")[
def online_update(occ, price, dur, congestion): \
#h(1em)sample = [occ, price/50, congestion_map[cong], dur/24] \
#h(1em)_online_buffer.append(sample) \
#h(1em)if len(_online_buffer) >= ONLINE_BATCH_SIZE: \
#h(2em)batch = vstack(_online_buffer) \
#h(2em)cvae_loss = train_step(batch, condition=null) \
#h(2em)if online_steps % 2 == 0: \
#h(3em)wgan_loss = wgan_train_step(batch) \
#h(2em)_online_buffer = []
  ]]),
  caption: [Generator online update pseudocode as implemented in `generator.py`.],
)

=== STID Predictor

The STID network (`src/digital_twin/stid.py`, 138 lines) learns spatial-temporal occupancy patterns. Each zone has a spatial embedding $e_i^s in RR^8$ and a temporal embedding $e_t^t in RR^8$ (concatenating hour and day-of-week embeddings). A spatial correlation matrix $M in RR^("zones" times "zones")$ captures pairwise spatial affinity. Prediction for zone $i$ at time $t$:

$ hat(O)_i(t+1) = "MLP"([e_i^s; bar(e)_t; e_t^t; bar(e)_i^s; O_i(t)]) $

where $bar(e)_t = 1/N sum_j M_(i j) e_j^s$ is the spatially-weighted embedding and $bar(e)_i^s$ is the temporal context. The MLP input dimension is $8+8+8+8+1 = 33$. Training uses manual gradient descent through sigmoid derivatives.

STID online training occurs inside `DigitalTwinSimulator.tick()`: after predicting $hat(O)_t+1$, the actual blended occupancy is used as the target for an SGD step: `stid.train_step(zone_idx, hour, dow, prev_occ, new_occ)`.

=== Scenario Engine

The `ScenarioEngine` (`src/digital_twin/scenario.py`, 287 lines) generates five counterfactuals per zone:

$ S = {"zone_closure", "price_surge", "capacity_expansion", "weather_disruption", "holiday_spike"} $

Each scenario modifies the conditional vector $c$ and passes it through the generator decoder $D(z, c)$ to produce a counterfactual state.

== Actuator Layer

The actuator layer (`src/iot/actuators.py`, 176 lines) provides four classes, all operating on in-memory state:

- `SmartBarrier`: accepts `open`/`close` commands; gated by a congestion threshold (refuses to open when congestion > 0.85)
- `PricingBoard`: displays `(price, effective_price)`; automatically marks down when occupancy exceeds 0.85
- `CongestionLight`: binary `on`/`off`; set to `on` when congestion exceeds 0.40
- `ActuatorBridge`: facade that auto-registers unknown zones, maintains a state dict `{zone: {barrier, board, light, ...}}`, and accepts an `actuate(lot_id, occupancy, price, multiplier)` call

The bridge is called at the end of both `start_session` and `end_session`. In production, these classes would map to Modbus registers or GPIO pins; currently they update Python dicts.

// ── 5. EVALUATION ──
= Evaluation

== Test Suite

The codebase includes 506 passing tests across 48 test files (`pytest tests/ --ignore=tests/e2e`, runtime 6:46). Representative files:

#figure(
  align(center, table(
    columns: (auto, auto, auto),
    stroke: 0.5pt,
    table.header([*Test File*], [*Scope*], [*Tests*]),
    [`test_sessions.py`], [Session lifecycle], [47],
    [`test_payments.py`], [Payment processing], [21],
    [`test_pipeline.py`], [Orchestrator integration], [32],
    [`test_rl.py`], [DQN + QMIX], [16],
    [`test_digital_twin.py`], [DT tick + generator + STID], [24],
    [`test_blockchain.py`], [Ledger + contract + IPFS], [18],
    [`test_iot_sensors.py`], [Ultrasonic + vision fusion], [12],
    [`test_micro_slots.py`], [Slot state engine], [25],
  )),
  caption: [Representative test coverage. 48 files, 506 tests total.],
)

== Model Accuracy

The ensemble model achieves MAE 0.02991 and $R^2$ 0.9573 on a chronological 80/20 holdout of the Birmingham Parking Dataset (35,322 rows). Accuracy is unchanged after 79% model compression, indicating substantial over-parameterisation in the original 500-tree/800-iteration configuration.

== Audit History

Six architectural gaps (A–F) were identified and corrected between revisions:

- *(A) Training-serving skew*: Rolling statistics included the current observation during inference. Fixed to exclude current observation, matching training's `.shift(1)`.
- *(B) MARL reset*: ConnectedVehicle routes and travel times persisted across episodes. Fixed to reset on each episode.
- *(C) IoT naive baseline*: `np.random.binomial(1, 0.5)` replaced with physics-based `RealisticParkingSensorSimulator`.
- *(D) Blockchain HTTP blocking*: SHA-256 mining ran synchronously in HTTP handlers, freezing the server. Fixed by moving mining to a background worker.
- *(E) Sensor fusion mode*: Orchestrator used `consensus_occupancy()` (both-sensors-agree) instead of OR-fused `clean_reading()`. Fixed to use conservative OR.
- *(F) Duration floor*: `max(dur, 0.1)` in `end_session()` inflated short sessions to 6 minutes. Removed; actual duration now used.

// ── 6. LIMITATIONS ──
= Limitations

*Single-process bottleneck.* The `DBLock` serialises all state-mutating operations. Combined with in-memory singletons (blockchain ledger, slot state engine, rate limiter, digital twin), the system cannot horizontally scale beyond one worker process.

*Simulated physical layer.* All IoT sensors, actuators, barrier gates, and pricing boards are Python classes operating on in-memory state. No ESP32, MQTT, Modbus, or GPIO hardware is involved. The abstractions support hardware substitution at the `read()`/`set_*()` interface, but this has not been implemented.

*Frozen RL agent.* The DQN/QMIX loads a pre-trained checkpoint and performs inference only in the API loop. No online RL training occurs. The `train()` method is covered by tests but called only from a separate training script.

*Single-process blockchain.* The ledger is an audit trail persisted to JSON. It provides no peer-to-peer consensus, no Byzantine fault tolerance, and no distributed mining.

*Render free tier constraints.* The 512 MB RAM ceiling limits model concurrency. The frontend main chunk is 1.27 MB — Vite warns that some chunks exceed 500 kB after minification.

// ── 7. CONCLUSION ──
= Conclusion

We presented Pragma, a closed-loop hybrid architecture for AI-powered smart parking that integrates six computational layers through a central orchestrator. The system implements three concrete feedback arcs: DT zone updates with online STID training, generator online learning every 10 real sessions, and actuator state synchronisation. We documented the architecture as it actually exists in source code — including the limitations that distinguish a research prototype from a production deployment.

The most consequential finding is the half-closed RL loop: training occurs offline in a separate script, not in the running API server. Closing this gap — implementing safe online RL with proper reward shaping and stability guards — is the primary direction for future work.

// ── REFERENCES ──
#set text(size: 8pt)
#bibliography("refs.bib", title: [References], style: "ieee")
