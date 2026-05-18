import numpy as np
from typing import List, Tuple, Dict
from .agent import NeuralAgent


class ConnectedVehicle:
    def __init__(self, vehicle_id: str, zone: int, destination: str):
        self.vehicle_id = vehicle_id
        self.zone = zone
        self.destination = destination
        self.is_connected = True
        self.travel_time = 0.0
        self.routed = False

    def __repr__(self):
        return f"CV({self.vehicle_id}, zone={self.zone}, dest={self.destination})"


class ZoneEnvironment:
    def __init__(self, zone_id: int, capacity: int, base_price: float = 10.0):
        self.zone_id = zone_id
        self.capacity = capacity
        self.occupancy = 0.0
        self.price = base_price
        self.history: List[float] = []

    def step(self, price_change: float) -> Tuple[float, float, float]:
        self.price = np.clip(self.price * (1 + price_change), 5, 50)
        elasticity = 0.8 * (self.price / 10.0)
        demand_impact = price_change * elasticity
        noise = np.random.normal(0, 0.02)
        self.occupancy = np.clip(self.occupancy - demand_impact + noise, 0, 1)
        self.history.append(self.occupancy)
        revenue = self.occupancy * self.capacity * self.price
        return self.occupancy, self.price, revenue


class QMIXMARL:
    def __init__(self, num_zones: int, zone_capacities: List[int]):
        self.num_zones = num_zones
        self.zones = [
            ZoneEnvironment(i, zone_capacities[i]) for i in range(num_zones)
        ]
        self.agents = [NeuralAgent(state_size=3) for _ in range(num_zones)]
        self.mixing_hidden = np.random.randn(num_zones, num_zones) * 0.1
        self.connected_vehicles: List[ConnectedVehicle] = []
        self.episode_rewards: List[float] = []

    def register_vehicles(self, vehicles: List[ConnectedVehicle]):
        self.connected_vehicles = vehicles

    def _get_global_state(self) -> np.ndarray:
        states = []
        for z in self.zones:
            states.extend([z.occupancy, z.price / 50.0])
        return np.array(states)

    def _compute_mixing(self, agent_qs: List[float]) -> float:
        q_vec = np.array(agent_qs)
        weights = np.abs(self.mixing_hidden @ q_vec)
        return float(np.sum(weights * q_vec) / (np.sum(weights) + 1e-8))

    def select_actions(self, train: bool = True) -> List[float]:
        actions = []
        for i, agent in enumerate(self.agents):
            state = np.array([
                self.zones[i].occupancy,
                self.zones[i].price / 50.0,
                0.5,
            ])
            action = agent.act(state, train=train)
            actions.append(action)
        return actions

    def step_all(self, actions: List[float]) -> Tuple[List[float], List[float], List[float]]:
        rewards = []
        occs = []
        revs = []
        for i, action in enumerate(actions):
            occ, price, rev = self.zones[i].step(action)
            occs.append(occ)
            revs.append(rev)
            if 0.6 <= occ <= 0.8:
                r = 20.0 + rev / 1000
            elif occ > 0.85:
                r = -50.0
            elif price > 30 and occ < 0.4:
                r = -100.0 * (price / 10.0)
            else:
                r = rev / 1000
            rewards.append(r)
        self._route_connected_vehicles(rewards)
        return occs, rewards, revs

    def _route_connected_vehicles(self, zone_rewards: List[float]):
        for cv in self.connected_vehicles:
            if cv.routed:
                continue
            best_zone = int(np.argmax(zone_rewards))
            cv.zone = best_zone
            cv.routed = True
            cv.travel_time = np.random.uniform(2, 8)

    def train_episode(self) -> Dict:
        actions = self.select_actions(train=True)
        occs, rewards, revs = self.step_all(actions)
        total_reward = sum(rewards)

        for i, agent in enumerate(self.agents):
            state = np.array([
                self.zones[i].occupancy,
                self.zones[i].price / 50.0,
                0.5,
            ])
            next_occ = self.zones[i].occupancy + np.random.normal(0, 0.01)
            next_state = np.array([next_occ, self.zones[i].price / 50.0, 0.5])
            agent.train(state, actions[i], rewards[i], next_state, done=False)

        mixing_q = self._compute_mixing(rewards)
        self.episode_rewards.append(total_reward)
        return {"total_reward": total_reward, "mixing_q": mixing_q, "occs": occs, "revs": revs}

    def train(self, episodes: int = 800):
        print("\n" + "=" * 60)
        print("MARL: Multi-Agent Deep RL Training")
        print("=" * 60)
        for ep in range(episodes):
            rand = np.random.rand()
            for i, zone in enumerate(self.zones):
                if rand < 0.4:
                    zone.occupancy = np.random.uniform(0.81, 0.98)
                elif rand < 0.7:
                    zone.occupancy = np.random.uniform(0.05, 0.35)
                else:
                    zone.occupancy = np.random.uniform(0.55, 0.85)
            result = self.train_episode()
            if (ep + 1) % 200 == 0:
                print(f"  Ep {ep+1:4d} | Reward: {result['total_reward']:+.2f} | "
                      f"OCC: {np.mean(result['occs']):.2f} | REV: ${np.mean(result['revs']):.2f}")
        print("MARL: Training complete\n")
        return self.episode_rewards

    def validate(self) -> Dict:
        high_states = [np.array([0.95, 10.0 / 50.0, 0.5]) for _ in self.agents]
        low_states = [np.array([0.15, 40.0 / 50.0, 0.5]) for _ in self.agents]
        high_actions = [a.act(s, train=False) for a, s in zip(self.agents, high_states)]
        low_actions = [a.act(s, train=False) for a, s in zip(self.agents, low_states)]
        return {
            "high_demand_actions": [f"{a:+.4f}" for a in high_actions],
            "low_demand_actions": [f"{a:+.4f}" for a in low_actions],
            "avg_high": float(np.mean(high_actions)),
            "avg_low": float(np.mean(low_actions)),
        }
