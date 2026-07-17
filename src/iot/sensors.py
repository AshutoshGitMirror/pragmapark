import uuid
import numpy as np
from dataclasses import dataclass, field
from collections import deque
from datetime import datetime
from typing import Optional, Tuple


@dataclass
class DualSensorReading:
    sensor_id: str
    lot_id: str
    timestamp: float
    slot_index: int
    ultrasonic_occupied: bool
    vision_occupied: bool
    confidence: float
    is_false_positive: bool = False
    vehicle_id: str = ""
    reading_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])


class UltrasonicSensor:
    def __init__(self, sensor_id: str, lot_id: str, noise_std: float = 0.05):
        self.sensor_id = sensor_id
        self.lot_id = lot_id
        self.noise_std = noise_std

    def read(
        self, ground_truth_occupied: bool, weather_factor: float = 0.0
    ) -> bool:
        if not ground_truth_occupied:
            false_positive_prob = 0.02 + weather_factor * 0.08
            return np.random.rand() > (1 - false_positive_prob)
        else:
            miss_prob = 0.03 + weather_factor * 0.05
            return np.random.rand() > miss_prob


class VisionSensor:
    def __init__(
        self, sensor_id: str, lot_id: str, lighting_factor: float = 1.0
    ):
        self.sensor_id = sensor_id
        self.lot_id = lot_id
        self.lighting_factor = lighting_factor

    def read(
        self, ground_truth_occupied: bool, weather_factor: float = 0.0
    ) -> Tuple[bool, float]:
        effective_lighting = self.lighting_factor * (
            1.0 - weather_factor * 0.4
        )
        if not ground_truth_occupied:
            fp_prob = 0.01 + (1.0 - effective_lighting) * 0.06
            detected = np.random.rand() > (1 - fp_prob)
        else:
            miss_prob = 0.02 + (1.0 - effective_lighting) * 0.08
            detected = np.random.rand() > miss_prob
        confidence = np.clip(
            effective_lighting * (0.95 - 0.2 * weather_factor)
            - 0.05 * (not detected),
            0.3,
            0.99,
        )
        return detected, confidence


class DualSensorPair:
    def __init__(self, lot_id: str, slot_count: int = 100):
        self.lot_id = lot_id
        self.slot_count = slot_count
        self.ultrasonic = UltrasonicSensor(f"us_{lot_id}", lot_id)
        self.vision = VisionSensor(f"vis_{lot_id}", lot_id)
        self.history: deque = deque(maxlen=1000)

    def sample(
        self,
        ground_truth_occupancy: np.ndarray,
        weather_factor: float = 0.0,
        dt: Optional[datetime] = None,
    ) -> list:
        dt = dt or datetime.now()
        readings = []
        batch = len(self.history)
        for i in range(self.slot_count):
            gt = (
                bool(ground_truth_occupancy[i])
                if i < len(ground_truth_occupancy)
                else False
            )
            us_occ = self.ultrasonic.read(gt, weather_factor)
            vis_occ, conf = self.vision.read(gt, weather_factor)
            fp = us_occ != vis_occ
            vid = f"VHCL-{self.lot_id}-{i:03d}-{batch:04d}" if gt else ""
            reading = DualSensorReading(
                sensor_id=f"{self.lot_id}/slot_{i}",
                lot_id=self.lot_id,
                timestamp=dt.timestamp(),
                slot_index=i,
                ultrasonic_occupied=us_occ,
                vision_occupied=vis_occ,
                confidence=conf,
                is_false_positive=fp,
                vehicle_id=vid,
            )
            readings.append(reading)
        self.history.append(readings)
        return readings

    def fuse_raw(
        self, ultrasonic_readings: list, vision_readings: list
    ) -> list:
        """Create DualSensorReading list from raw sensor boolean arrays.

        Used by the ingestion API to run dual-sensor fusion on incoming
        sensor telemetry before persisting occupancy records.
        """
        readings = []
        for i, (us, vis) in enumerate(
            zip(ultrasonic_readings, vision_readings)
        ):
            readings.append(
                DualSensorReading(
                    sensor_id=f"{self.lot_id}/slot_{i}",
                    lot_id=self.lot_id,
                    timestamp=0.0,
                    slot_index=i,
                    ultrasonic_occupied=bool(us),
                    vision_occupied=bool(vis),
                    confidence=0.95 if us == vis else 0.5,
                    is_false_positive=(us != vis),
                )
            )
        return readings

    def consensus_occupancy(self, readings: list) -> float:
        """Return the fraction of slots both sensors agree are occupied."""
        agreed_occupied = sum(
            1
            for r in readings
            if r.ultrasonic_occupied == r.vision_occupied
            and r.ultrasonic_occupied
        )
        total = len(readings)
        return agreed_occupied / total if total > 0 else 0.0

    def false_positive_rate(self, readings: list) -> float:
        disagreements = sum(1 for r in readings if r.is_false_positive)
        return disagreements / len(readings) if readings else 0.0

    def clean_reading(self, readings: list) -> np.ndarray:
        """Fuse dual-sensor readings into occupancy via conservative OR.

        Paper: "conservative OR fusion ensuring a space is marked
        occupied if either sensor detects an obstacle, minimizing
        false negatives."
        Both-sensors-agree cases pass through; disagreement → occupied.
        """
        cleaned = []
        for r in readings:
            if r.ultrasonic_occupied and r.vision_occupied:
                cleaned.append(1.0)
            elif not r.ultrasonic_occupied and not r.vision_occupied:
                cleaned.append(0.0)
            else:
                # Disagreement: conservative OR — if either sensor detects
                # an obstacle, mark as occupied. Minimizes false negatives
                # at the cost of slightly higher false positive rate.
                # Paper: O_fused = O_ultra OR O_vision
                cleaned.append(1.0)
        return np.array(cleaned)
