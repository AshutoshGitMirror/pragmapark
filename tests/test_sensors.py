import numpy as np
from src.iot.sensors import UltrasonicSensor, VisionSensor, DualSensorPair


class TestUltrasonicSensor:
    def test_read_occupied_returns_bool(self):
        s = UltrasonicSensor("us_1", "lot_1")
        for _ in range(50):
            r = s.read(True)
            assert isinstance(r, bool)

    def test_read_empty_returns_bool(self):
        s = UltrasonicSensor("us_1", "lot_1")
        for _ in range(50):
            r = s.read(False)
            assert isinstance(r, bool)


class TestVisionSensor:
    def test_read_returns_tuple(self):
        s = VisionSensor("vis_1", "lot_1")
        for _ in range(50):
            detected, conf = s.read(True)
            assert isinstance(detected, bool)
            assert 0.3 <= conf <= 0.99

    def test_read_empty(self):
        s = VisionSensor("vis_1", "lot_1")
        for _ in range(50):
            detected, conf = s.read(False)
            assert isinstance(detected, bool)
            assert conf >= 0.3


class TestDualSensorPair:
    def test_constructor(self):
        pair = DualSensorPair("lot_1", slot_count=50)
        assert pair.lot_id == "lot_1"
        assert pair.slot_count == 50

    def test_sample_returns_readings(self):
        pair = DualSensorPair("lot_1", slot_count=10)
        gt = np.random.binomial(1, 0.5, 10)
        readings = pair.sample(gt)
        assert len(readings) == 10
        for r in readings:
            assert r.lot_id == "lot_1"
            assert isinstance(r.ultrasonic_occupied, bool)
            assert isinstance(r.vision_occupied, bool)

    def test_consensus_occupancy_between_0_and_1(self):
        pair = DualSensorPair("lot_1", slot_count=10)
        gt = np.random.binomial(1, 0.5, 10)
        readings = pair.sample(gt)
        occ = pair.consensus_occupancy(readings)
        assert 0.0 <= occ <= 1.0

    def test_false_positive_rate_between_0_and_1(self):
        pair = DualSensorPair("lot_1", slot_count=10)
        gt = np.random.binomial(1, 0.5, 10)
        readings = pair.sample(gt)
        fpr = pair.false_positive_rate(readings)
        assert 0.0 <= fpr <= 1.0

    def test_clean_reading_returns_ndarray(self):
        pair = DualSensorPair("lot_1", slot_count=10)
        gt = np.random.binomial(1, 0.5, 10)
        readings = pair.sample(gt)
        cleaned = pair.clean_reading(readings)
        assert len(cleaned) == 10
        assert all(v in (0.0, 1.0) for v in cleaned)

    def test_consensus_full_agreement(self):
        np.random.seed(42)
        pair = DualSensorPair("lot_1", slot_count=3)
        readings = pair.sample(np.array([1, 1, 1]))
        occ = pair.consensus_occupancy(readings)
        # All sensors agree occupied when ground truth is 1
        assert occ == 1.0, (
            f"Expected 1.0 consensus, got {occ} (random sensor noise)"
        )

    def test_history_accumulates(self):
        pair = DualSensorPair("lot_1", slot_count=5)
        assert len(pair.history) == 0
        pair.sample(np.random.binomial(1, 0.5, 5))
        assert len(pair.history) == 1
