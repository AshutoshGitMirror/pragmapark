"""Dual-sensor IoT layer with false-positive awareness."""

import numpy as np


class DualSensorPair:
    def __init__(self, lot_id: str, slot_count: int = 5):
        self.lot_id = lot_id
        self.slot_count = slot_count
        self.history = []

    def sample(self, ground_truth: np.ndarray, weather_factor: float = 0.0) -> dict:
        sensor_a_noise = np.random.beta(2, 20, self.slot_count)
        sensor_b_noise = np.random.beta(2, 20, self.slot_count)
        a_readings = np.clip(ground_truth.astype(float) + sensor_a_noise + weather_factor * 0.1, 0, 1)
        b_readings = np.clip(ground_truth.astype(float) + sensor_b_noise + weather_factor * 0.15, 0, 1)
        reading = {
            "sensor_a": a_readings.tolist(),
            "sensor_b": b_readings.tolist(),
            "ground_truth": ground_truth.tolist(),
            "weather_factor": round(weather_factor, 4),
        }
        self.history.append(reading)
        return reading

    def consensus_occupancy(self, reading: dict) -> float:
        a = np.array(reading["sensor_a"])
        b = np.array(reading["sensor_b"])
        consensus = (a + b) / 2
        return float(np.mean(consensus > 0.5))

    def false_positive_rate(self, reading: dict) -> float:
        a = np.array(reading["sensor_a"])
        b = np.array(reading["sensor_b"])
        gt = np.array(reading["ground_truth"])
        fp_a = np.mean((a > 0.5) & (gt == 0)) if gt.sum() < len(gt) else 0.0
        fp_b = np.mean((b > 0.5) & (gt == 0)) if gt.sum() < len(gt) else 0.0
        return float((fp_a + fp_b) / 2)
