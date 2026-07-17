"""Local CV agent: a small FastAPI service that runs the YOLO detector,
maps vehicles onto per-lot slot ROIs, and pushes REAL occupancy to
Render's ingestion endpoint as the ``sensor`` role.

Run with::

    uvicorn src.cv.agent:app --port 8777

or via ``python -m src.cv.cli``. The agent never imports torch at
module load; the detector pulls it in lazily on first detection.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .detector import DEFAULT_MODEL, Detector
from .roi import RoiStore
from .ultrasonic import FileUltrasonicSource, SimulatedUltrasonicSource, UltrasonicSource

AGENT_PORT = int(os.environ.get("CV_AGENT_PORT", "8777"))
BACKEND_URL = os.environ.get("PRAGMA_BACKEND", "https://pragma-4szs.onrender.com").rstrip("/")
# Per-sensor API key (X-Sensor-Key). A sensor key is issued to a lot owner
# via POST /api/v1/sensors and is bound to exactly one lot.
CV_SENSOR_KEY = os.environ.get("CV_SENSOR_KEY", "")
CV_LOT_ID = os.environ.get("CV_LOT_ID", "")

# COCO vehicle box -> our reading schema.
_READING_FIELDS = ("slot_id", "occupied", "confidence")


class DetectRequest(BaseModel):
    lot_id: str
    image_path: Optional[str] = None
    image_b64: Optional[str] = None  # URL-safe base64 PNG/JPEG
    ultrasonic_source: Optional[str] = None  # path for real ultrasonic feed
    iou_threshold: float = 0.1


class PushRequest(DetectRequest):
    backend_url: Optional[str] = None
    sensor_key: Optional[str] = None


def _decode_b64_image(data: str):
    import base64

    import numpy as np
    from PIL import Image
    from io import BytesIO

    # Strip optional data-URI prefix.
    if "," in data:
        data = data.split(",", 1)[1]
    raw = base64.urlsafe_b64decode(data + "===")
    img = Image.open(BytesIO(raw)).convert("RGB")
    return np.asarray(img)


class Agent:
    """Holds the detector + ROI store and orchestrates detect/push."""

    def __init__(
        self,
        model_path: str = DEFAULT_MODEL,
        backend_url: str = BACKEND_URL,
        store: Optional[RoiStore] = None,
        sensor_key: Optional[str] = None,
        lot_id: Optional[str] = None,
    ):
        self.detector = Detector(model_path=model_path)
        self.store = store or RoiStore()
        self.backend_url = backend_url
        self.sensor_key = sensor_key
        self.lot_id = lot_id

    def detect(self, lot_id: str, image, ultrasonic_source: Optional[UltrasonicSource] = None,
               iou_threshold: float = 0.1) -> Dict[str, Any]:
        slots = self.store.get_slots(lot_id)
        if not slots:
            raise HTTPException(
                status_code=404,
                detail=f"No slot ROIs configured for lot '{lot_id}'. Calibrate first.",
            )
        boxes = self.detector.detect(image)
        occupancy = self.store_occupancy(lot_id, slots, boxes, iou_threshold)
        ultrasonic = None
        if ultrasonic_source is not None:
            ultrasonic = ultrasonic_source.read(len(slots))
        return {
            "lot_id": lot_id,
            "boxes": boxes,
            "slot_count": len(slots),
            "occupancy": occupancy,
            "ultrasonic": ultrasonic,
        }

    @staticmethod
    def store_occupancy(lot_id, slots, boxes, iou_threshold):
        from .roi import map_boxes_to_slots

        occ = map_boxes_to_slots(boxes, slots, iou_threshold=iou_threshold)
        readings = [
            {"slot_id": s.slot_id, "occupied": bool(occ.get(s.slot_id, False)), "confidence": 1.0}
            for s in slots
        ]
        return readings

    def push(self, lot_id: str, image, ultrasonic_source: Optional[UltrasonicSource] = None,
               iou_threshold: float = 0.1, sensor_key: Optional[str] = None,
               backend_url: Optional[str] = None) -> Dict[str, Any]:
        backend = backend_url or self.backend_url
        resolved_lot = lot_id or self.lot_id or ""
        key = sensor_key or self.sensor_key
        if not key:
            raise HTTPException(
                status_code=500,
                detail="CV_SENSOR_KEY not configured (issue one via POST /api/v1/sensors).",
            )
        result = self.detect(lot_id, image, ultrasonic_source, iou_threshold)

        vision = result["occupancy"]
        n = result["slot_count"]
        # Explicit "no hardware" placeholder so the backend's conservative-OR
        # fusion reduces to pure vision (no synthetic fallback).
        ultrasonic = result["ultrasonic"]
        if ultrasonic is None:
            ultrasonic = [False] * n

        payload = {
            "lot_id": resolved_lot,
            "ultrasonic_readings": ultrasonic,
            "vision_readings": vision,
        }
        import requests

        resp = requests.post(
            f"{backend}/api/v1/ingestion/sensor-readings",
            json=payload,
            headers={"X-Sensor-Key": key},
            timeout=30,
        )
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"Backend push failed ({resp.status_code}): {resp.text[:300]}",
            )
        return {"pushed": True, "backend_status": resp.status_code, "reading": payload}


app = FastAPI(title="Pragma CV Agent", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_agent = Agent()


@app.get("/status")
def status():
    return {
        "ok": True,
        "backend": _agent.backend_url,
        "model": _agent.detector.model_path,
        "lots": _agent.store.list_lots(),
    }


@app.get("/lots")
def list_lots():
    return {"lots": _agent.store.list_lots()}


@app.get("/slots/{lot_id}")
def get_slots(lot_id: str):
    slots = _agent.store.get_slots(lot_id)
    return {"lot_id": lot_id, "slots": [s.__dict__ for s in slots]}


@app.post("/detect")
def detect(req: DetectRequest):
    image = None
    if req.image_b64:
        image = _decode_b64_image(req.image_b64)
    elif req.image_path:
        image = req.image_path
    else:
        raise HTTPException(status_code=400, detail="Provide image_path or image_b64.")
    source = None
    if req.ultrasonic_source:
        source = FileUltrasonicSource(req.ultrasonic_source)
    return _agent.detect(req.lot_id, image, source, req.iou_threshold)


@app.post("/push")
def push(req: PushRequest):
    image = None
    if req.image_b64:
        image = _decode_b64_image(req.image_b64)
    elif req.image_path:
        image = req.image_path
    else:
        raise HTTPException(status_code=400, detail="Provide image_path or image_b64.")
    source = None
    if req.ultrasonic_source:
        source = FileUltrasonicSource(req.ultrasonic_source)
    return _agent.push(
        req.lot_id,
        image,
        source,
        req.iou_threshold,
        req.sensor_key,
        req.backend_url,
    )


def _main():
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=AGENT_PORT)


if __name__ == "__main__":
    _main()
