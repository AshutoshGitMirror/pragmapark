"""Camera capture + annotation loop for the local CV agent.

Runs a background thread that grabs frames (real webcam via cv2, or a
synthetic test pattern when no camera/torch is available), runs vehicle
detection, maps boxes onto per-lot slot ROIs, and exposes:

* ``mjpeg``  — multipart JPEG stream for the Live Vision UI feed
* ``get_occupancy(lot_id)`` — latest per-slot occupied state
* ``get_latest_frame()`` — last BGR frame (used by ``push/live``)

cv2 / torch are imported lazily so this module loads even without the
heavy deps installed (offline dev / unit tests).
"""

from __future__ import annotations

import base64
import threading
import time
from typing import Dict, List, Optional

import numpy as np

from .roi import map_boxes_to_slots

# A minimal valid 1x1 JPEG, used as a static placeholder when cv2 is not
# installed (offline dev) so the MJPEG stream and <img> feed still render.
_PLACEHOLDER_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8U"
    "HRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA"
    "/8QAFAABAAAAAAAAAAAAAAAAAAAAA//EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEA"
    "AD8AfwD/2Q=="
)


class CameraManager:
    """Owns the capture thread and the latest annotated frame."""

    def __init__(self, agent, camera_id: int = 0, fps: int = 10):
        self.agent = agent
        self.camera_id = camera_id
        self.fps = fps
        self.available = False
        self.frame: Optional[np.ndarray] = None
        self.frame_size: List[int] = [640, 480]
        self.occupancy: Dict[str, List[dict]] = {}
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._cap = None
        self._synthetic_t = 0.0

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:  # nosec B110
                pass
            self._cap = None

    def _open_camera(self) -> bool:
        try:
            import cv2

            cap = cv2.VideoCapture(self.camera_id)
            if cap.isOpened():
                self.available = True
                self._cap = cap
                return True
        except Exception:  # nosec B110
            pass
        self.available = False
        return False

    # -- frame acquisition ------------------------------------------------
    def _grab(self) -> np.ndarray:
        if self._cap is not None:
            ok, frame = self._cap.read()
            if ok and frame is not None:
                return frame
        # Synthetic fallback so the UI still has something to render.
        h, w = self.frame_size[1], self.frame_size[0]
        t = self._synthetic_t
        self._synthetic_t += 0.05
        img = np.zeros((h, w, 3), dtype=np.uint8)
        for y in range(h):
            img[y, :, 0] = int(18 + 36 * (y / h))
        try:
            import cv2

            bx = int(w * 0.5 + w * 0.3 * np.sin(t))
            by = int(h * 0.62)
            cv2.rectangle(img, (bx - 34, by - 22), (bx + 34, by + 22), (0, 200, 255), 2)
        except Exception:  # nosec B110
            pass
        return img

    def _run(self) -> None:
        self._open_camera()
        while self._running:
            frame = self._grab()
            boxes: List[List[float]] = []
            try:
                boxes = self.agent.detector.detect(frame)
            except Exception:
                boxes = []
            occ: Dict[str, List[dict]] = {}
            for lot_id in self.agent.store.list_lots():
                slots = self.agent.store.get_slots(lot_id)
                if not slots:
                    continue
                mapped = map_boxes_to_slots(boxes, slots, iou_threshold=0.1)
                occ[lot_id] = [
                    {
                        "slot_id": s.slot_id,
                        "occupied": bool(mapped.get(s.slot_id, False)),
                        "confidence": 1.0,
                    }
                    for s in slots
                ]
            out = self._draw(frame, boxes, occ)
            with self._lock:
                self.frame = out
                self.occupancy = occ
                self.frame_size = [int(frame.shape[1]), int(frame.shape[0])]
            time.sleep(1.0 / self.fps)

    def _draw(self, frame: np.ndarray, boxes, occ) -> np.ndarray:
        try:
            import cv2

            out = frame.copy()
            for lot_id in occ:
                slots = self.agent.store.get_slots(lot_id)
                for s in slots:
                    pts = np.array(s.polygon, dtype=np.int32).reshape((-1, 1, 2))
                    occupied = next(
                        (o["occupied"] for o in occ[lot_id] if o["slot_id"] == s.slot_id),
                        False,
                    )
                    color = (0, 200, 90) if not occupied else (70, 70, 220)
                    cv2.polylines(out, [pts], True, color, 2)
            for b in boxes:
                x1, y1, x2, y2 = (int(v) for v in b)
                cv2.rectangle(out, (x1, y1), (x2, y2), (240, 200, 40), 2)
            return out
        except Exception:
            return frame

    # -- accessors ---------------------------------------------------------
    def get_latest_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            return None if self.frame is None else self.frame.copy()

    def get_frame_jpeg(self) -> bytes:
        with self._lock:
            f = self.frame
        if f is None:
            h, w = self.frame_size[1], self.frame_size[0]
            f = np.zeros((h, w, 3), dtype=np.uint8)
        try:
            import cv2

            ok, buf = cv2.imencode(".jpg", f)
            if not ok:
                return b""
            return buf.tobytes()
        except Exception:
            # cv2 not installed (offline dev): serve a static placeholder so
            # the MJPEG stream / <img> feed still renders something.
            return _PLACEHOLDER_JPEG

    def get_occupancy(self, lot_id: str):
        with self._lock:
            return list(self.occupancy.get(lot_id, [])), list(self.frame_size)

    def mjpeg(self):
        self.start()
        try:
            while True:
                data = self.get_frame_jpeg()
                if data:
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n" + data + b"\r\n"
                    )
                time.sleep(1.0 / self.fps)
        except GeneratorExit:
            return
