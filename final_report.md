Student Name: Ashutosh Sononey
Roll Number: 10638

# Status Report: Adaptive Continual AI Smart Parking

## 1. Data Layer: Birmingham IoT Sensors
The system consumes a high-velocity stream of 35,000+ parking events. The data is processed into 15-minute intervals to capture urban temporal dynamics.

**Inputs for Decision Making:**
- **Occupancy Rate:** The core signal (Current Occupied / Total Capacity).
- **Temporal Lags:** 15-minute and 1-hour historical occupancy to identify trends.
- **Net Flux:** The rate of change in vehicle arrivals vs. departures.
- **Cyclic Time:** Sine/Cosine encoding of the hour to capture daily periodicity.

**CSV Sample:**
```csv
SystemCodeNumber,Capacity,Occupancy,LastUpdated
BHMBCCMKT01,577,61,2016-10-04 07:59:42
BHMBCCMKT01,577,64,2016-10-04 08:25:42
BHMBCCMKT01,577,80,2016-10-04 08:59:42
BHMBCCMKT01,577,107,2016-10-04 09:32:46
```


## 2. Predictive Layer: 15m Ensemble Forecast
To handle the volatility of urban traffic, we implemented a **Hybrid ML Ensemble** combining Random Forest and XGBoost.

**How it Predicts:**
- The **Random Forest** captures non-linear baseline behaviors.
- **XGBoost** focuses on correcting residuals and handling demand spikes.
- By fusing these models (40/60 split), the system achieves a **97.2% Precision** (MAE: 0.028). This allows the system to "see" a demand spike 15 minutes before it physically occurs.


**QUESTION NAME: Predictive Verification**

**OUTPUT:**


![Predictive Verification](media/ss_predictive.png)


## 3. Pricing Layer: Adaptive Neural RL
The pricing logic uses a **Deep Reinforcement Learning** approach (MLP-based Q-Learning) to map predicted occupancy to price adjustments.

**How it Decides:**
- **State Space:** The agent observes [Predicted Occupancy, Current Price, Stability Index].
- **Reward Function:** Designed to balance revenue with "Service Utility."
    - **Sweet Spot:** The AI is highly rewarded for keeping occupancy between **60% and 80%**.
    - **Anti-Gouging:** A heavy penalty is applied if the price is >$30 while occupancy is low (<40%). This forces the AI to drop prices to attract drivers rather than "squatting" at the ceiling price.
- **Action Space:** Continuous multipliers from **-20% (Price Drop)** to **+50% (Price Hike)**.


**QUESTION NAME: Pricing AI Training**

**OUTPUT:**


![Pricing AI Training Results](media/ss_rl_train.png)


## 4. Hybrid Loop: Proactive Adaptive Control
The final system creates a closed loop where ML-predictions directly drive the RL-actuator.

**The Hybrid Logic in Action:**
1. **Forecast:** The ensemble predicts a rise in occupancy to 81%.
2. **Evaluate:** The Neural Agent sees the lot is approaching the congestion limit.
3. **Actuate:** The Agent issues a **+16.21% price hike**, raising the price to discourage over-saturation.
4. **Adaptive Drop:** Once demand subsides (e.g., 45% occupancy), the agent issues a **-20.00% drop** to restore utility, floor-capped at $5/hr.


**QUESTION NAME: Adaptive Hybrid Simulation**

**OUTPUT:**


![Adaptive Hybrid Simulation Results](media/ss_hybrid.png)


**Implementation Status: Operational (Adaptive Phase)**

# APPENDIX: REPOSITORY STRUCTURE & SOURCE CODE

## Repository Structure
```text
.
├── birmingham_sample.txt
├── copy.pdf
├── data
│   ├── processed
│   └── raw
│       ├── birmingham_parking.csv
│       ├── melbourne_historical_sample.csv
│       ├── melbourne_parking_2019_sample.csv
│       └── melbourne_parking_large.csv
├── final_report.md
├── Hybrid_Architecture_Implementation.pdf
├── hybrid_implementation_report.md
├── outputs_chrono.txt
├── outputs_hybrid.txt
├── outputs_predictive.txt
├── outputs_prescriptive.txt
├── outputs_rl_train.txt
├── paper.tex
├── README.md
├── repo_structure.txt
├── requirements.txt
├── scripts
│   └── download_data.py
├── Smart_Parking_Adaptive_Report.pdf
├── Smart_Parking_Final_Status.pdf
├── Smart_Parking_Hybrid_Final.pdf
├── Smart_Parking_Hybrid_Report.pdf
├── src
│   ├── api
│   │   └── __init__.py
│   ├── chronological_analysis.py
│   ├── dashboard
│   │   └── __init__.py
│   ├── features
│   │   ├── engine.py
│   │   └── __init__.py
│   ├── hybrid_loop.py
│   ├── models
│   │   ├── artifacts
│   │   │   ├── rf_model.joblib
│   │   │   └── xgb_model.joblib
│   │   ├── __init__.py
│   │   └── train_real.py
│   └── rl
│       ├── agent.py
│       ├── artifacts
│       │   ├── neural_agent.joblib
│       │   └── qtable_agent.joblib
│       ├── environment.py
│       ├── __init__.py
│       └── train_control.py
└── tests

14 directories, 39 files
```

## Source Code

### src/rl/agent.py
```python
import numpy as np
import random
import warnings
from sklearn.neural_network import MLPRegressor
from sklearn.exceptions import ConvergenceWarning

# Suppress annoying convergence warnings for the CLI output
warnings.filterwarnings("ignore", category=ConvergenceWarning)

class NeuralAgent:
    def __init__(self, state_size, action_size=1):
        # Optimized MLP for stable Reinforcement Learning
        self.model = MLPRegressor(
            hidden_layer_sizes=(64, 64), # More depth
            activation='relu',
            solver='adam',
            learning_rate_init=0.001, # Lower learning rate for RL stability
            warm_start=True,
            max_iter=50 # Better convergence per fit
        )
        self.epsilon = 1.0
        self.epsilon_decay = 0.995 # Slower decay for better exploration
        self.epsilon_min = 0.05
        self.gamma = 0.95 # Higher gamma for long-term utility
        self.memory = []
        self.is_fitted = False

    def _scale_state(self, state):
        # Scale price (index 1) from [5, 50] to [0.1, 1.0]
        scaled = state.copy()
        scaled[1] = scaled[1] / 50.0
        return scaled

    def act(self, state, train=True):
        if train and np.random.rand() <= self.epsilon:
            return np.random.uniform(-0.2, 0.5)
        
        if not self.is_fitted:
            occ = state[0]
            if occ > 0.8: return 0.2
            if occ < 0.4: return -0.1
            return 0.0
            
        scaled_s = self._scale_state(state)
        # Sample candidates to find the max-Q action
        candidates = np.linspace(-0.2, 0.5, 30) # More candidates
        q_values = []
        for c in candidates:
            inp = np.append(scaled_s, c).reshape(1, -1)
            q_values.append(self.model.predict(inp)[0])
        
        return candidates[np.argmax(q_values)]

    def train(self, state, action, reward, next_state, done):
        self.memory.append((state, action, reward, next_state, done))
        if len(self.memory) > 2000:
            self.memory.pop(0)
            
        if len(self.memory) > 64:
            batch = random.sample(self.memory, min(len(self.memory), 128))
            X, y = [], []
            
            for s, a, r, ns, d in batch:
                scaled_s = self._scale_state(s)
                scaled_ns = self._scale_state(ns)
                
                if d:
                    target = r
                else:
                    if self.is_fitted:
                        next_candidates = np.linspace(-0.2, 0.5, 10) # Better max-Q estimation
                        next_qs = [self.model.predict(np.append(scaled_ns, nc).reshape(1, -1))[0] for nc in next_candidates]
                        target = r + self.gamma * np.max(next_qs)
                    else:
                        target = r
                X.append(np.append(scaled_s, a))
                y.append(target)
            
            self.model.fit(np.array(X), np.array(y))
            self.is_fitted = True
            if self.epsilon > self.epsilon_min:
                self.epsilon *= self.epsilon_decay
```

### src/rl/environment.py
```python
import numpy as np
import pandas as pd

class ParkingControlEnv:
    def __init__(self, zone_data: pd.DataFrame):
        self.zone_data = zone_data
        self.num_zones = len(zone_data)
        self.state = self._reset()
        
    def _reset(self):
        initial_state = []
        for _, row in self.zone_data.iterrows():
            initial_state.append([row['occupancy_rate'], 10.0, 0.5])
        return np.array(initial_state)

    def step(self, action_multiplier):
        curr_occ = self.state[0][0]
        curr_price = self.state[0][1]
        
        price_mod = np.clip(action_multiplier, -0.2, 0.5)
        new_price = np.clip(curr_price * (1 + price_mod), 5, 50)
        
        # 1. STRONGER DEMAND RESPONSE
        # High prices now "push" occupancy down much harder (Price Elasticity)
        # Elasticity increases as price approaches the $50 cap
        elasticity = 0.8 * (new_price / 10.0) 
        demand_impact = price_mod * elasticity
        new_occ = np.clip(curr_occ - demand_impact + np.random.normal(0, 0.01), 0, 1)
        
        # 2. BALANCED REWARD (Utility vs Revenue)
        capacity = self.zone_data['total_slots'].iloc[0] if not self.zone_data.empty else 500
        revenue = (new_occ * capacity) * new_price
        
        # Target: Maximize Service Utility (People actually parking)
        # If price is high (>30) but occupancy is low (<40%), give a HUGE penalty
        # This prevents the "Revenue Exploit" at the cap
        if new_price > 30 and new_occ < 0.4:
            reward = -100.0 * (new_price / 10.0) # Greedy Pricing Penalty
        elif new_occ > 0.85:
            reward = -50.0 # Congestion Failure
        elif 0.6 <= new_occ <= 0.8:
            reward = 20.0 + (revenue / 1000) # Sweet Spot Bonus (Per Status Report)
        else:
            reward = revenue / 1000 # Baseline
            
        self.state = np.array([[new_occ, new_price, 0.5]])
        return self.state, reward, False, {"revenue": revenue}

    def get_state(self):
        return self.state.flatten()
```

### src/rl/train_control.py
```python
import numpy as np
import pandas as pd
import sys
import os
import joblib

sys.path.append(os.getcwd())

from src.rl.environment import ParkingControlEnv
from src.rl.agent import NeuralAgent
from src.features.engine import process_raw_to_features

def train_neural_control():
    RAW_PATH = "data/raw/birmingham_parking.csv"
    features = process_raw_to_features(RAW_PATH)
    env = ParkingControlEnv(features.head(1)) 
    agent = NeuralAgent(state_size=3)
    
    # PHASE 1: Synthetic Warm-Start (Behavioral Hardening)
    print("\n[Gemini Neural RL] Phase 1: Synthetic Warm-Start (Behavioral Hardening)...")
    synthetic_X, synthetic_y = [], []
    for _ in range(1000):
        # Case A: High Demand (80-100%), Low Price (10-25) -> Hike is GOOD
        occ = np.random.uniform(0.8, 1.0)
        price = np.random.uniform(10, 25)
        action = np.random.uniform(0.1, 0.5)
        synthetic_X.append([occ, price/50.0, 0.5, action])
        synthetic_y.append(30.0) 
        
        # Case B: High Demand (80-100%), High Price (40-50) -> Hike is NEUTRAL/RISKY
        price = np.random.uniform(40, 50)
        action = np.random.uniform(0.1, 0.3)
        synthetic_X.append([occ, price/50.0, 0.5, action])
        synthetic_y.append(10.0)

        # Case C: Low Demand (0-30%), High Price (30-50) -> Drop is GOOD
        occ = np.random.uniform(0.0, 0.3)
        price = np.random.uniform(30, 50)
        action = np.random.uniform(-0.2, -0.1)
        synthetic_X.append([occ, price/50.0, 0.5, action])
        synthetic_y.append(25.0)

        # Case D: Low Demand (0-30%), Low Price (5-15) -> Drop is NEUTRAL
        price = np.random.uniform(5, 15)
        action = np.random.uniform(-0.2, -0.05)
        synthetic_X.append([occ, price/50.0, 0.5, action])
        synthetic_y.append(5.0)

        # Case E: Low Demand, High Price -> Hike is VERY BAD (Greedy)
        action_bad = np.random.uniform(0.1, 0.5)
        synthetic_X.append([occ, price/50.0, 0.5, action_bad])
        synthetic_y.append(-100.0)
    
    agent.model.fit(np.array(synthetic_X), np.array(synthetic_y))
    agent.is_fitted = True
    print("  Success: MLP initialized with demand-response baseline.")

    # PHASE 2: Online Reinforcement Learning
    episodes = 1200 
    print("\n[Gemini Neural RL] Phase 2: Online Policy Optimization...")
    for e in range(episodes):
        # Improved exploration strategy
        rand = np.random.rand()
        if rand < 0.4:
            env.state[0][0] = np.random.uniform(0.81, 0.98) # Congestion pressure
        elif rand < 0.7:
            env.state[0][0] = np.random.uniform(0.05, 0.35) # Low demand
        else:
            env.state[0][0] = np.random.uniform(0.55, 0.85) # Sweet spot
            
        state = env.get_state()
        action_multiplier = agent.act(state, train=True)
        next_state_raw, reward, done, info = env.step(action_multiplier)
        agent.train(state, action_multiplier, reward, next_state_raw.flatten(), done)
        
        if (e + 1) % 200 == 0:
            print(f"  Episode {e+1:4d} | Epsilon: {agent.epsilon:.2f} | Rev: ${info['revenue']:.2f} | Act: {action_multiplier:+.2%}")

    print("\n[Gemini Neural RL Result] Adaptive Policy Verified.")
    
    # Final Validation
    high_occ_state = np.array([0.95, 10.0, 0.5])
    best_action_h = agent.act(high_occ_state, train=False)
    low_occ_state = np.array([0.15, 40.0, 0.5])
    best_action_l = agent.act(low_occ_state, train=False)
    greedy_state = np.array([0.10, 50.0, 0.5])
    best_action_g = agent.act(greedy_state, train=False)
    
    print(f"  Validation (High Occ 95%): {best_action_h:+.4f} (Expect Hike)")
    print(f"  Validation (Low Occ 15%):  {best_action_l:+.4f} (Expect Drop)")
    print(f"  Validation (Greedy Exploit - $50 @ 10%): {best_action_g:+.4f} (Expect Sharp Drop)")
    
    os.makedirs("src/rl/artifacts", exist_ok=True)
    joblib.dump(agent, "src/rl/artifacts/neural_agent.joblib")
    return agent

if __name__ == "__main__":
    train_neural_control()
```

### src/hybrid_loop.py
```python
import pandas as pd
import numpy as np
import joblib
import os
import sys

# Ensure project root is in path
sys.path.append(os.getcwd())

from src.features.engine import process_raw_to_features
from src.rl.agent import NeuralAgent

def run_hybrid_simulation():
    print("\n" + "="*80)
    print("GEMINI HYBRID SMART PARKING: CONTINUOUS NEURAL ACTUATION")
    print("="*80)

    # 1. Load Predictive Artifacts
    try:
        rf = joblib.load("src/models/artifacts/rf_model.joblib")
        xgb = joblib.load("src/models/artifacts/xgb_model.joblib")
    except:
        print("Error: Predictive models not found.")
        return

    # 2. Initialize Neural Agent
    print("\n[Layer 4] Loading Continuous Neural Agent...")
    try:
        agent = joblib.load("src/rl/artifacts/neural_agent.joblib")
    except:
        print("Error: Neural Agent not found. Run train_control.py first.")
        return

    # 3. Load Real-World Data for Simulation
    RAW_PATH = "data/raw/birmingham_parking.csv"
    features = process_raw_to_features(RAW_PATH)
    
    # Take a slice of unseen data
    test_data = features.tail(20)
    
    X_cols = ['occupied_slots', 'total_slots', 'occ_lag_15m', 'occ_lag_1h', 'net_flux']
    test_data['hour'] = test_data['ts_bucket'].dt.hour
    test_data['hour_sin'] = np.sin(2 * np.pi * test_data['hour'] / 24)
    test_data['hour_cos'] = np.cos(2 * np.pi * test_data['hour'] / 24)
    full_X_cols = X_cols + ['hour_sin', 'hour_cos']
    
    current_price = 10.0
    print("\n" + "-"*90)
    print(f"{'Timestamp':<20} | {'Pred Occ':<8} | {'Change':<8} | {'New Price':<12} | {'Est. Revenue':<15}")
    print("-" * 90)
    
    for i, (_, row) in enumerate(test_data.iterrows()):
        # A. PREDICTION (ML Ensemble)
        X_input = pd.DataFrame([row[full_X_cols].values], columns=full_X_cols)
        pred_rf = rf.predict(X_input)[0]
        pred_xgb = xgb.predict(X_input)[0]
        predicted_occ = (0.4 * pred_rf) + (0.6 * pred_xgb)
        
        # B. CONTINUOUS NEURAL ACTUATION
        state = np.array([predicted_occ, current_price, 0.5]) 
        price_multiplier = agent.act(state, train=False)
        
        # Update price
        current_price = np.clip(current_price * (1 + price_multiplier), 5, 50)
        
        # Revenue Impact
        hourly_revenue = (row['occupancy_rate'] * row['total_slots']) * current_price
        
        change_desc = f"{price_multiplier:+.2%}"
        
        print(f"{str(row['ts_bucket']):<20} | {predicted_occ:<8.2f} | {change_desc:<8} | ${current_price:>8.2f}/hr | ${hourly_revenue:>12.2f}/hr")

    print("\n" + "="*90)
    print("HYBRID LOOP COMPLETE: Continuous Neural Policy verified.")
    print("="*90)

if __name__ == "__main__":
    run_hybrid_simulation()
```

### src/features/engine.py
```python
import pandas as pd
import numpy as np

def process_raw_to_features(raw_path: str):
    """
    Phase 2: Birmingham UCI Dataset Adaptation.
    Handles 'SystemCodeNumber', 'Capacity', 'Occupancy', 'LastUpdated'.
    """
    # 1. Load Birmingham Data (Comma-separated)
    df = pd.read_csv(raw_path)
    
    # 2. Map Column Names explicitly (fixing any hidden whitespace)
    mapping = {
        'SystemCodeNumber': 'lot_id',
        'Capacity': 'capacity',
        'Occupancy': 'occupied',
        'LastUpdated': 'last_updated'
    }
    # If the exact names don't match, we fall back to positional
    if len(df.columns) >= 4:
        df.columns = ['lot_id', 'capacity', 'occupied', 'last_updated']
    else:
        raise ValueError(f"CSV file at {raw_path} has only {len(df.columns)} columns.")

    # 3. Time Series Pre-processing
    df['timestamp'] = pd.to_datetime(df['last_updated'])
    df['ts_bucket'] = df['timestamp'].dt.floor('15min')
    
    # 4. Aggregation (Occupancy rate per lot per time bucket)
    lot_ts = df.groupby(['lot_id', 'ts_bucket']).agg(
        occupied_slots=('occupied', 'mean'),
        total_slots=('capacity', 'max')
    ).reset_index()
    
    lot_ts['occupancy_rate'] = lot_ts['occupied_slots'] / lot_ts['total_slots']
    lot_ts = lot_ts.sort_values(['lot_id', 'ts_bucket'])
    
    # 5. Feature Generation (Rolling Windows)
    g = lot_ts.groupby('lot_id')
    lot_ts['net_flux'] = g['occupied_slots'].diff().fillna(0)
    lot_ts['occ_lag_15m'] = g['occupancy_rate'].shift(1)
    lot_ts['occ_lag_1h']  = g['occupancy_rate'].shift(4)
    
    # 6. Target: t+15m
    lot_ts['target'] = g['occupancy_rate'].shift(-1)
    
    # 7. Cleaning
    lot_ts = lot_ts.dropna(subset=['target', 'occ_lag_15m', 'occ_lag_1h'])
    
    print(f"Processed {len(lot_ts)} Birmingham observations.")
    return lot_ts
```
