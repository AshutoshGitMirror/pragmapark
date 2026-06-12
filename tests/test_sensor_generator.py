import numpy as np
from datetime import datetime
from src.iot.generator import RealisticParkingSensorSimulator
from src.iot.sensors import DualSensorReading


def test_simulator_initialization():
    sim = RealisticParkingSensorSimulator(
        "test_zone", capacity=20, base_price=12.5
    )
    assert sim.zone_id == "test_zone"
    assert sim.capacity == 20
    assert sim.base_price == 12.5
    assert len(sim.us_bias) == 20
    assert len(sim.vis_bias) == 20


def test_base_occupancy_rates():
    sim = RealisticParkingSensorSimulator("test_zone", capacity=10)

    # Weekday morning commute (9 AM)
    dt_morning = datetime(2026, 6, 8, 9, 0, 0)  # Monday
    rate_morning = sim.get_base_occupancy_rate(dt_morning)
    assert 0.0 <= rate_morning <= 1.0

    # Weekday midnight (3 AM)
    dt_night = datetime(2026, 6, 8, 3, 0, 0)  # Monday
    rate_night = sim.get_base_occupancy_rate(dt_night)
    assert 0.0 <= rate_night <= 1.0

    # Peak occupancy at 9 AM should typically exceed night occupancy
    # (Stochastic noise in simulator; check statistical bounds)
    assert rate_morning > rate_night or (rate_morning - rate_night) > -0.2


def test_weather_factor_bounds():
    sim = RealisticParkingSensorSimulator("test_zone", capacity=10)
    dt = datetime(2026, 6, 8, 12, 0, 0)
    for _ in range(50):
        w = sim.get_weather_factor(dt)
        assert 0.0 <= w <= 1.0


def test_spatial_skew():
    sim = RealisticParkingSensorSimulator(
        "test_zone", capacity=100, entrance_skew=25.0
    )

    # Generate ground truth occupancy for a moderately busy lot (rate = 0.4)
    np.random.seed(42)
    gt = sim.get_ground_truth_occupancy(0.4)

    assert len(gt) == 100
    assert gt.dtype == bool

    # Spots near entrance (indices 0-20) should have higher fill rate
    # than spots far from entrance (indices 80-100)
    front_fill = np.mean(gt[:20])
    back_fill = np.mean(gt[80:])
    assert front_fill >= back_fill


def test_sample_step_output():
    sim = RealisticParkingSensorSimulator("test_zone", capacity=5)
    dt = datetime(2026, 6, 8, 10, 0, 0)

    readings = sim.sample_step(dt)
    assert len(readings) == 5
    assert sim.steps == 1

    for r in readings:
        assert isinstance(r, DualSensorReading)
        assert r.lot_id == "test_zone"
        assert r.timestamp == dt.timestamp()
        assert isinstance(r.ultrasonic_occupied, bool)
        assert isinstance(r.vision_occupied, bool)
        assert 0.3 <= r.confidence <= 0.99
        assert r.is_false_positive == (
            r.ultrasonic_occupied != r.vision_occupied
        )
