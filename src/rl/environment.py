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
