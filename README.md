# Smart Parking Implementation Status

## Project Status: ACTIVE
We have successfully implemented the **Predictive** and **Pricing** components of the Hybrid Smart Parking architecture.

### 1. Data/IoT Layer
We use real-world sensor data from Birmingham to track parking occupancy. The system is set up to handle time-series data without "cheating" (no look-ahead bias).

### 2. Predictive Layer (The Forecast)
We built an AI ensemble that looks at historical patterns to predict the future.
- **Accuracy:** 97.2% (Mean Error of 2.8%)
- **Capability:** Predicts occupancy 15 minutes into the future.

### 3. Pricing RL (The Action)
We trained a Reinforcement Learning agent to manage prices. 
- **Goal:** Automatically increase prices when the Predictive Layer forecasts a shortage.
- **Guardrails:** The system has a hard floor of **$5/hr** and a ceiling of **$50/hr** to ensure economic stability.
- **Why RL?** Unlike a static `systemd` timer or a simple if-else loop, the RL agent learns a **Policy**. It optimizes the price based on both the *forecasted demand* and the *current price state*, maximizing a reward function that balances revenue against congestion.

### 4. The Closed Loop
The `hybrid_loop.py` script connects the Forecast to the Pricing AI.
 This means the system now takes **proactive action** based on what it thinks will happen next.

---
## How to Run
1. **Full Simulation:** `.venv/bin/python3 src/hybrid_loop.py`
2. **Forecast Test:** `.venv/bin/python3 src/chronological_analysis.py`
3. **AI Training:** `.venv/bin/python3 src/rl/train_control.py`

*Note: The Blockchain Ledger layer is a planned future upgrade.*
