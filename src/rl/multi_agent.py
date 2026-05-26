import numpy as np
from typing import List, Tuple, Dict
from .agent import NeuralAgent

ELASTICITY_BASE = 0.15
ELASTICITY_MIN = 0.10
ELASTICITY_MAX = 0.30


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


class NonConnectedVehicle:
    def __init__(self, vehicle_id: str, zone: int, destination: str):
        self.vehicle_id = vehicle_id
        self.zone = zone
        self.destination = destination
        self.is_connected = False
        self.travel_time = 0.0
        self.routed = False

    def __repr__(self):
        return f"NCV({self.vehicle_id}, zone={self.zone}, dest={self.destination})"


class ZoneEnvironment:
    def __init__(self, zone_id: int, capacity: int, base_price: float = 10.0):
        self.zone_id = zone_id
        self.capacity = capacity
        self.occupancy = 0.0
        self.price = base_price
        self.history: List[float] = []

    def step(self, price_change: float) -> Tuple[float, float, float]:
        self.price = np.clip(self.price * (1 + price_change), 5, 50)
        elasticity_abs = np.clip(ELASTICITY_BASE * (self.price / 10.0), ELASTICITY_MIN, ELASTICITY_MAX)
        demand_impact = price_change * elasticity_abs
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
        self.mixing_weights = np.ones(num_zones) / num_zones
        self.mixing_lr = 0.01
        self.connected_vehicles: List[ConnectedVehicle] = []
        self.episode_rewards: List[float] = []
        self.td_errors: List[float] = []

    def register_vehicles(self, vehicles: List[ConnectedVehicle]):
        self.connected_vehicles = vehicles

    def _compute_qtot(self, agent_qs: List[float]) -> float:
        qs = np.array(agent_qs)
        w = np.abs(self.mixing_weights)
        w = w / (w.sum() + 1e-8)
        return float(np.dot(w, qs))

    def select_actions(self, train: bool = True) -> List[float]:
        actions = []
        for i, agent in enumerate(self.agents):
            state = np.array([
                self.zones[i].occupancy,
                self.zones[i].price,
                0.5,
            ])
            action = agent.act(state, train=train)
            actions.append(action)
        return actions

    def _compute_agent_qs(self, actions: List[float]) -> List[float]:
        qs = []
        for i, agent in enumerate(self.agents):
            state = np.array([self.zones[i].occupancy, self.zones[i].price, 0.5])
            if agent.is_fitted:
                scaled_s = agent._scale_state(state)
                inp = np.append(scaled_s, actions[i]).reshape(1, -1)
                qs.append(float(agent.model.predict(inp)[0]))
            else:
                qs.append(0.0)
        return qs

    def step_all(self, actions: List[float]) -> Tuple[List[float], List[float], List[float]]:
        rewards = []
        occs = []
        revs = []
        for i, action in enumerate(actions):
            occ, price, rev = self.zones[i].step(action)
            occs.append(occ)
            revs.append(rev)
            revenue_norm = rev / 10000
            occ_bonus = 0.5 if 0.6 <= occ <= 0.8 else 0.0
            congestion_penalty = -1.0 if occ > 0.85 else 0.0
            greedy_penalty = -2.0 if price > 30 and occ < 0.4 else 0.0
            r = revenue_norm + occ_bonus + congestion_penalty + greedy_penalty
            rewards.append(r)
        self._route_connected_vehicles(occs)
        return occs, rewards, revs

    def _route_connected_vehicles(self, zone_occs: List[float]):
        routing_counts = [0] * len(zone_occs)
        for cv in self.connected_vehicles:
            if cv.routed:
                routing_counts[cv.zone] += 1
                continue
            effective_vacancy = [
                max(0.0, 1.0 - zone_occs[i] - 0.02 * routing_counts[i])
                for i in range(len(zone_occs))
            ]
            best_zone = int(np.argmax(effective_vacancy))
            cv.zone = best_zone
            cv.routed = True
            routing_counts[best_zone] += 1
            cv.travel_time = np.random.uniform(2, 8)

    def train_episode(self) -> Dict:
        pre_step_states = [
            np.array([self.zones[i].occupancy, self.zones[i].price, 0.5])
            for i in range(self.num_zones)
        ]
        actions = self.select_actions(train=True)
        occs, rewards, revs = self.step_all(actions)

        post_step_states = [
            np.array([self.zones[i].occupancy, self.zones[i].price, 0.5])
            for i in range(self.num_zones)
        ]

        q_values = self._compute_agent_qs(actions)
        qtot = self._compute_qtot(q_values)

        next_actions = self.select_actions(train=False)
        next_qs = self._compute_agent_qs(next_actions)
        next_qtot = self._compute_qtot(next_qs)
        td_target = sum(rewards) + self.agents[0].gamma * next_qtot
        td_error = td_target - qtot
        self.td_errors.append(abs(td_error))

        for i, agent in enumerate(self.agents):
            agent.train(pre_step_states[i], actions[i], rewards[i], post_step_states[i], done=False)

        w_grad = td_error * np.array(q_values)
        self.mixing_weights = np.clip(self.mixing_weights + self.mixing_lr * w_grad, 0.01, None)
        self.mixing_weights /= self.mixing_weights.sum()
        self.episode_rewards.append(qtot)

        for agent in self.agents:
            agent.decay_epsilon()

        return {
            "total_reward": sum(rewards), "qtot": qtot, "td_error": float(td_error),
            "occs": occs, "revs": revs, "mixing_weights": self.mixing_weights.tolist(),
        }

    def train(self, episodes: int = 800):
        print("\n" + "=" * 60)
        print("MARL: Multi-Agent Deep RL Training (learnable mixing)")
        print("=" * 60)
        for ep in range(episodes):
            for i, zone in enumerate(self.zones):
                zone.price = 10.0
                rand = np.random.rand()
                if rand < 0.4:
                    zone.occupancy = np.random.uniform(0.81, 0.98)
                elif rand < 0.7:
                    zone.occupancy = np.random.uniform(0.05, 0.35)
                else:
                    zone.occupancy = np.random.uniform(0.55, 0.85)
            result = self.train_episode()
            if (ep + 1) % 200 == 0:
                print(f"  Ep {ep+1:4d} | Q_tot: {result['qtot']:+.2f} | "
                      f"TD: {result['td_error']:.4f} | OCC: {np.mean(result['occs']):.2f} | "
                      f"REV: ${np.mean(result['revs']):.2f} | "
                      f"mix_w: [{result['mixing_weights'][0]:.2f} ...]")
        print("MARL: Training complete\n")
        return self.episode_rewards

    def validate(self) -> Dict:
        high_states = [np.array([0.95, 10.0, 0.5]) for _ in self.agents]
        low_states = [np.array([0.15, 40.0, 0.5]) for _ in self.agents]
        high_actions = [a.act(s, train=False) for a, s in zip(self.agents, high_states)]
        low_actions = [a.act(s, train=False) for a, s in zip(self.agents, low_states)]
        mixed_states = [
            np.array([0.95 if i % 2 == 0 else 0.15, 10.0, 0.5])
            for i in range(self.num_zones)
        ]
        mixed_actions = [a.act(s, train=False) for a, s in zip(self.agents, mixed_states)]
        return {
            "high_demand_actions": [f"{a:+.4f}" for a in high_actions],
            "low_demand_actions": [f"{a:+.4f}" for a in low_actions],
            "mixed_actions": [f"{a:+.4f}" for a in mixed_actions],
            "avg_high": float(np.mean(high_actions)),
            "avg_low": float(np.mean(low_actions)),
            "avg_mixed": float(np.mean(mixed_actions)),
            "mixing_weights": [f"{w:.4f}" for w in self.mixing_weights],
        }
