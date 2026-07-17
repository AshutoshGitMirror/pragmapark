import pytest
import sys
import os
import numpy as np

sys.path.append(os.getcwd())

from src.rl.agent import NeuralAgent  # noqa: E402
from src.rl.environment import ParkingControlEnv  # noqa: E402
from src.rl.multi_agent import (  # noqa: E402
    QMIXMARL, ConnectedVehicle, ZoneEnvironment,
)
from src.features.engine import process_raw_to_features  # noqa: E402


@pytest.fixture
def sample_features():
    return process_raw_to_features("data/raw/birmingham_parking.csv")


class TestNeuralAgent:
    def test_agent_initialization(self):
        agent = NeuralAgent(state_size=4)
        assert agent.epsilon == 1.0
        assert not agent.is_fitted

    def test_agent_act_before_training(self):
        agent = NeuralAgent(state_size=4)
        action = agent.act(np.array([0.5, 10.0, 0.5, 0.0]), train=False)
        assert isinstance(action, float)
        assert -0.2 <= action <= 0.5

    def test_agent_act_high_occupancy(self):
        agent = NeuralAgent(state_size=4)
        action = agent.act(np.array([0.95, 10.0, 0.5, 0.0]), train=False)
        assert action >= 0

    def test_agent_act_low_occupancy(self):
        agent = NeuralAgent(state_size=4)
        action = agent.act(np.array([0.15, 10.0, 0.5, 0.0]), train=False)
        assert action <= 0

    def test_agent_training(self):
        agent = NeuralAgent(state_size=4)
        agent.train(
            np.array([0.5, 10.0, 0.5, 0.0]),
            0.1,
            10.0,
            np.array([0.6, 12.0, 0.5, 0.0]),
            False,
        )
        assert len(agent.memory) == 1

    def test_agent_experience_replay(self):
        agent = NeuralAgent(state_size=4)
        for _ in range(100):
            agent.train(
                np.random.rand(4),
                np.random.uniform(-0.2, 0.5),
                np.random.randn(),
                np.random.rand(4),
                False,
            )
        assert len(agent.memory) == 100


class TestParkingEnvironment:
    def test_env_initialization(self, sample_features):
        env = ParkingControlEnv(sample_features.head(1))
        state = env.get_state()
        assert len(state) == 4

    def test_env_step(self, sample_features):
        env = ParkingControlEnv(sample_features.head(1))
        state, reward, done, info = env.step(0.2)
        assert 5 <= state[0][1] <= 50
        assert isinstance(reward, float)
        assert "revenue" in info

    def test_env_price_elasticity(self, sample_features):
        env = ParkingControlEnv(sample_features.head(1))
        _, _, _, info_high = env.step(0.5)
        env.state = np.array([[0.5, 10.0, 0.5, 0.0]])
        _, _, _, info_low = env.step(-0.2)
        assert info_high["revenue"] >= 0


class TestMARL:
    def test_qmix_initialization(self):
        marl = QMIXMARL(4, [500, 300, 400, 200])
        assert marl.num_zones == 4
        assert len(marl.zones) == 4

    def test_zone_environment(self):
        zone = ZoneEnvironment(0, 500)
        occ, price, rev = zone.step(0.1)
        assert 0 <= occ <= 1
        assert 5 <= price <= 50
        assert rev >= 0

    def test_connected_vehicle(self):
        cv = ConnectedVehicle("CV_1", 0, "downtown")
        assert cv.is_connected
        assert not cv.routed

    def test_marl_action_selection(self):
        marl = QMIXMARL(2, [500, 300])
        actions = marl.select_actions(train=False)
        assert len(actions) == 2

    def test_marl_training_step(self):
        marl = QMIXMARL(2, [500, 300])
        result = marl.train_episode()
        assert "total_reward" in result
        assert isinstance(result["total_reward"], float)

    def test_marl_validation(self):
        marl = QMIXMARL(4, [500, 300, 400, 200])
        val = marl.validate()
        assert "high_demand_actions" in val
        assert "low_demand_actions" in val

    def test_marl_vehicle_routing(self):
        marl = QMIXMARL(3, [500, 300, 400])
        vehicles = [
            ConnectedVehicle(f"CV_{i}", 0, "downtown") for i in range(5)
        ]
        marl.register_vehicles(vehicles)
        actions = marl.select_actions(train=False)
        occs, rewards, revs = marl.step_all(actions)
        assert len(occs) == 3
        assert len(rewards) == 3
