import numpy as np


class QMIXMARL:
    def __init__(self, n_agents: int = 3, state_dim: int = 3, action_dim: int = 3):
        self.n_agents = n_agents
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.agents = []
        self.routing_counts = [0] * n_agents

    def add_agent(self, agent):
        self.agents.append(agent)

    def select_actions(self, states: list, epsilon: float = 0.0) -> list:
        actions = []
        for i, (agent, state) in enumerate(zip(self.agents, states)):
            agent.epsilon = epsilon
            a = agent.act(state, train=True)
            actions.append(a)
        return actions

    def route_vehicle(self, zone_occupancies: list) -> int:
        if not self.agents:
            return 0
        occupancies = np.array(zone_occupancies)
        if len(occupancies) != len(self.agents):
            return 0
        effective_capacity = [
            max(0, 1.0 - occ) - 0.01 * self.routing_counts[i]
            for i, occ in enumerate(occupancies)
        ]
        total_cap = sum(effective_capacity)
        if total_cap <= 0:
            return int(np.argmin(occupancies))
        probs = [c / total_cap for c in effective_capacity]
        chosen = int(np.random.choice(len(self.agents), p=probs))
        self.routing_counts[chosen] += 1
        return chosen

    def decay_all(self, factor: float = 0.995):
        for agent in self.agents:
            agent.decay_epsilon(factor)

    def train_all(self):
        losses = []
        for agent in self.agents:
            loss = agent.train()
            if loss is not None:
                losses.append(loss)
        return np.mean(losses) if losses else 0.0

    def reset_routing(self):
        self.routing_counts = [0] * self.n_agents
