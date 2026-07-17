"""Lazy YOLOv8 vehicle detector.

Wraps a pretrained COCO YOLOv8 model and returns only vehicle
bounding boxes (cars / motorcycles / buses / trucks). Module-level
import is torch-free: ``ultralytics`` / ``torch`` are imported lazily
inside :meth:`Detector._ensure` so the rest of ``src.cv`` (geometry,
ultrasonic, unit tests) works without the heavy deps installed.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# COCO class indices we treat as "occupying" vehicles.
# car=2, motorcycle=3, bus=5, truck=7 (0-indexed COCO).
VEHICLE_CLASSES: Dict[int, str] = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

# Default model artifact (downloaded on first use by ultralytics).
DEFAULT_MODEL = "yolov8n.pt"

Box = List[float]  # [x1, y1, x2, y2] in pixel coordinates


class Detector:
    """Thin, lazy wrapper around an ultralytics YOLO model.

    The model is loaded on first :meth:`detect` call, not at import time,
    so a machine without torch can still import the module (and the tests
    that never call ``detect`` stay offline-clean).
    """

    def __init__(
        self,
        model_path: str = DEFAULT_MODEL,
        conf: float = 0.25,
        device: str = "cpu",
    ):
        self.model_path = model_path
        self.conf = conf
        self.device = device
        self._model: Any = None

    def _ensure(self):
        if self._model is not None:
            return
        try:
            from ultralytics import YOLO  # lazy: heavy deps
        except ImportError as exc:  # pragma: no cover - depends on install
            raise RuntimeError(
                "ultralytics/torch not installed. Install from "
                "requirements-cv.txt before running detection."
            ) from exc
        self._model = YOLO(self.model_path)

    def detect(self, image) -> List[Box]:
        """Run detection on a single frame.

        ``image`` may be a file path (str) or a numpy array (H x W x 3,
        BGR as produced by OpenCV). Returns a list of ``[x1, y1, x2, y2]``
        boxes in integer pixel coordinates, filtered to vehicle classes.
        """
        self._ensure()
        results = self._model.predict(
            source=image,
            conf=self.conf,
            device=self.device,
            verbose=False,
        )
        boxes: List[Box] = []
        for res in results:
            for b in res.boxes:
                cls = int(b.cls.item())
                if cls not in VEHICLE_CLASSES:
                    continue
                x1, y1, x2, y2 = (float(v) for v in b.xyxy[0].tolist())
                boxes.append([x1, y1, x2, y2])
        return boxes
