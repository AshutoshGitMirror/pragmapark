import numpy as np
from datetime import datetime
from typing import List
from src.iot.sensors import DualSensorReading


class RealisticParkingSensorSimulator:
    """Realistic time-series synthetic IoT sensor data generator.

    Models:
    - Temporal patterns (business hour commutes, day/night cycles,
      weekends).
    - Spatial patterns (entrance proximity filling sequence).
    - Physical sensor signal model for ultrasonic distance
      readings (noise + dropouts + drift).
    - Physical camera model (ambient light dependency, weather
      degradation, occlusions).
    - Environmental interference (stochastic weather factor and
      rain/storm noise bursts).
    - Pure NumPy implementation.
    """

    def __init__(
        self,
        zone_id: str,
        capacity: int,
        base_price: float = 10.0,
        entrance_skew: float = 15.0,
        us_noise_std: float = 0.05,
        us_dropout_prob: float = 0.01,
        us_drift_rate: float = 0.0001,
        vis_occlusion_prob: float = 0.02,
        vis_drift_rate: float = -0.0001,
    ):
        self.zone_id = zone_id
        self.capacity = capacity
        self.base_price = base_price
        self.entrance_skew = entrance_skew

        # Sensor noise settings
        self.us_noise_std = us_noise_std
        self.us_dropout_prob = us_dropout_prob
        self.us_drift_rate = us_drift_rate
        self.vis_occlusion_prob = vis_occlusion_prob
        self.vis_drift_rate = vis_drift_rate

        # Initialize physical sensor thresholds
        self.D_floor = 3.0  # distance to floor (meters)
        self.D_car = 1.0  # distance to car roof (meters)
        self.D_threshold = 2.0  # distance detection threshold (meters)

        # Track cumulative sensor degradation (drift/bias) for each slot
        self.us_bias = np.zeros(capacity)
        self.vis_bias = np.zeros(capacity)

        # Counter for step tracking in streaming
        self.steps = 0

    def get_base_occupancy_rate(self, dt: datetime) -> float:
        """Model realistic diurnal and weekly occupancy patterns.

        Weekdays: Dual commute peaks (morning 9 AM, evening 6 PM).
        Weekends: Single broad leisure peak (afternoon 2 PM).
        """
        hour = dt.hour + dt.minute / 60.0 + dt.second / 3600.0
        weekday = dt.weekday()  # 0=Monday, 6=Sunday
        is_weekend = weekday >= 5

        if not is_weekend:
            # Dual-peak Gaussian commute pattern
            morning_peak = np.exp(-((hour - 9.0) ** 2) / (2 * (1.8**2)))
            evening_peak = np.exp(-((hour - 18.0) ** 2) / (2 * (2.2**2)))
            occ_rate = 0.12 + 0.68 * (
                0.45 * morning_peak + 0.55 * evening_peak
            )
        else:
            # Weekend peak (broad afternoon distribution)
            weekend_peak = np.exp(-((hour - 14.0) ** 2) / (2 * (3.5**2)))
            occ_rate = 0.10 + 0.75 * weekend_peak

        # Add small diurnal random walk noise
        state_noise = np.random.normal(0, 0.02)
        return float(np.clip(occ_rate + state_noise, 0.0, 1.0))

    def get_weather_factor(self, dt: datetime) -> float:
        """Generate time-varying weather factor for rain/snow/storm.

        Outputs value in [0, 1]. Higher value causes heavier
        sensor degradation. Includes diurnal variance and transient
        storm bursts.
        """
        # Base weather factor using seasonal sinusoid (higher in winter/autumn
        # months)
        base = 0.1 + 0.15 * np.sin(2 * np.pi * (dt.month - 6) / 12)

        # Occasional storm burst (e.g., afternoon storms on days multiple of 4)
        is_storm = (dt.day % 4 == 0) and (13 <= dt.hour <= 16)
        if is_storm:
            storm_intensity = 0.6 + 0.3 * np.random.rand()
            return float(np.clip(storm_intensity, 0.0, 1.0))

        noise = np.random.uniform(-0.05, 0.05)
        return float(np.clip(base + noise, 0.0, 1.0))

    def get_ground_truth_occupancy(
        self, base_rate: float
    ) -> np.ndarray:
        """Simulate spatial patterns where spots closer to the
        entrance (low index) fill first.

        P(occupied_slot_i) = sigmoid(
            entrance_skew * (base_rate - i / capacity)
        )
        """
        indices = np.arange(self.capacity)
        normalized_indices = indices / self.capacity

        # Shift sigmoid center based on current lot occupancy rate
        logits = self.entrance_skew * (base_rate - normalized_indices)
        probabilities = 1.0 / (1.0 + np.exp(-logits))

        # Sample ground truth occupancy states via Bernoulli trials
        gt = np.random.rand(self.capacity) < probabilities
        return gt.astype(bool)

    def sample_step(self, dt: datetime) -> List[DualSensorReading]:
        """Perform a single step of the streaming sensor simulation.

        Applies signal models, sensor noise, occlusion, and bias drift.
        Returns a list of DualSensorReadings.
        """
        self.steps += 1

        # 1. Update cumulative drift bias per slot
        # Ultrasonic drifts positive (raising distance read), Vision drifts
        # negative (lowering confidence)
        self.us_bias += np.random.normal(
            self.us_drift_rate, 0.0001, self.capacity
        )
        self.vis_bias += np.random.normal(
            self.vis_drift_rate, 0.0001, self.capacity
        )

        # 2. Get baseline state variables
        base_rate = self.get_base_occupancy_rate(dt)
        weather = self.get_weather_factor(dt)
        ground_truth = self.get_ground_truth_occupancy(base_rate)

        # 3. Ambient lighting model (0.1 for pitch black night, 1.0 for noon)
        hour = dt.hour + dt.minute / 60.0
        if 6 <= hour <= 18:
            ambient_light = 0.2 + 0.8 * np.sin(np.pi * (hour - 6) / 12)
        else:
            ambient_light = 0.2

        # Effectively scale sensor parameters based on current weather factor
        us_noise_eff = self.us_noise_std * (1.0 + 3.0 * weather)
        us_dropout_eff = self.us_dropout_prob * (1.0 + 5.0 * weather)
        vis_occlusion_eff = self.vis_occlusion_prob + 0.18 * weather

        readings = []
        for i in range(self.capacity):
            gt = bool(ground_truth[i])

            # --- A. Ultrasonic Sensor Signal Model ---
            is_us_dropout = np.random.rand() < us_dropout_eff
            if is_us_dropout:
                # Dropout means we fail to get a reflection, returning empty
                # floor distance
                dist = self.D_floor
            else:
                base_dist = self.D_car if gt else self.D_floor
                dist = (
                    base_dist
                    + np.random.normal(0, us_noise_eff)
                    + self.us_bias[i]
                )

            # Binary occupancy decision by thresholding distance
            us_occupied = bool(dist < self.D_threshold)

            # --- B. Vision Sensor / Camera Signal Model ---
            is_vis_occluded = np.random.rand() < vis_occlusion_eff

            if is_vis_occluded:
                # Occluded camera yields 50% random guess and lowest confidence
                vis_occupied = bool(np.random.rand() < 0.5)
                vis_confidence = 0.5
            else:
                # Camera accuracy degrades based on dark conditions and bad
                # weather
                accuracy = 0.98 * ambient_light * (1.0 - 0.25 * weather)
                accuracy = float(np.clip(accuracy, 0.55, 0.99))

                # Sample classification success/failure
                if gt:
                    vis_occupied = bool(np.random.rand() < accuracy)
                else:
                    vis_occupied = bool(np.random.rand() > accuracy)

                # Confidence degrades in poor light/weather, plus bias drift
                raw_conf = accuracy - 0.1 * np.random.rand() + self.vis_bias[i]
                vis_confidence = float(np.clip(raw_conf, 0.3, 0.99))

            # Disagreement means it is classified as a false positive candidate
            is_false_positive = us_occupied != vis_occupied

            vid = f"VHCL-{self.zone_id}-{i:03d}-{self.steps:04d}" if gt else ""
            reading = DualSensorReading(
                sensor_id=f"{self.zone_id}/slot_{i}",
                lot_id=self.zone_id,
                timestamp=dt.timestamp(),
                slot_index=i,
                ultrasonic_occupied=us_occupied,
                vision_occupied=vis_occupied,
                confidence=vis_confidence,
                is_false_positive=is_false_positive,
                vehicle_id=vid,
            )
            readings.append(reading)

        return readings
