"""Pluggable ultrasonic source.

The bundled implementation is a clearly-labelled SIMULATION: there is no
ultrasonic hardware in this project, so the ultrasonic leg is a dummy
interface. The agent pushes real vision only; when no real ultrasonic
feed is attached it sends an explicit "no hardware" placeholder so the
backend's conservative-OR fusion reduces to pure vision.

A real deployment can subclass ``UltrasonicSource`` and supply data via
``--ultrasonic-source`` (e.g. a JSON/CSV stream from ESP32+HC-SR04
sensors) without changing any other code.
"""

from __future__ import annotations

import csv
import json
import os
from abc import ABC, abstractmethod
from typing import List


class UltrasonicSource(ABC):
    """Interface for an ultrasonic occupancy source."""

    @abstractmethod
    def read(self, slot_count: int) -> List[bool]:
        """Return per-slot ultrasonic occupancy (True = occupied)."""
        raise NotImplementedError


class SimulatedUltrasonicSource(UltrasonicSource):
    """LABELLED SIMULATION only.

    Generates plausible-but-fake occupancy so the dual-sensor pipeline
    has something to fuse when no camera/hardware is present (demo mode).
    This is NOT real data and must never be presented as such.
    """

    def __init__(self, seed: int = 1, base_rate: float = 0.4):
        self.seed = seed
        self.base_rate = base_rate
        self._state: List[bool] = []

    def read(self, slot_count: int) -> List[bool]:
        import random

        random.seed(self.seed + len(self._state))
        out: List[bool] = []
        for i in range(slot_count):
            prev = self._state[i] if i < len(self._state) else False
            # Simple sticky random walk around the base rate.
            p = self.base_rate + (0.2 if prev else -0.1)
            p = max(0.0, min(1.0, p))
            occupied = random.random() < p  # nosec B311
            out.append(occupied)
        self._state = out
        return out


class FileUltrasonicSource(UltrasonicSource):
    """Adapter for a REAL ultrasonic feed stored as JSON or CSV.

    JSON: a list of booleans, or {"slots": [bool, ...]}.
    CSV: one row, columns are per-slot 0/1 (or true/false).

    This is the seam where genuine hardware would plug in.
    """

    def __init__(self, path: str):
        self.path = path
        if not os.path.exists(path):
            raise FileNotFoundError(f"Ultrasonic source file not found: {path}")

    def read(self, slot_count: int) -> List[bool]:
        with open(self.path, "r", encoding="utf-8") as fh:
            text = fh.read().strip()
        if self.path.endswith(".csv"):
            reader = csv.reader([text])
            row = next(reader)
            values = [v.strip().lower() in ("1", "true", "yes") for v in row]
        else:
            data = json.loads(text)
            values = data["slots"] if isinstance(data, dict) and "slots" in data else data
        values = list(values)
        if len(values) != slot_count:
            # Pad/truncate defensively; real feeds must match slot count.
            if len(values) < slot_count:
                values = values + [False] * (slot_count - len(values))
            else:
                values = values[:slot_count]
        return [bool(v) for v in values]
