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
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .camera import CameraManager
from .detector import DEFAULT_MODEL, Detector
from .roi import RoiStore, SlotROI, suggest_grid
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


class GridSuggestRequest(BaseModel):
    lot_id: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    rows: int
    cols: int
    margin: float = 0.05


class SaveSlotsRequest(BaseModel):
    lot_id: str
    slots: List[Dict[str, Any]]  # each: {"slot_id": int, "polygon": [[x,y], ...]}


class SetPolygonRequest(BaseModel):
    lot_id: str
    slot_id: int
    polygon: List[List[float]]


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
        # Background capture + annotation loop feeding the Live Vision UI.
        self.camera = CameraManager(self)

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
        "camera": {
            "available": _agent.camera.available,
            "frame_size": _agent.camera.frame_size,
        },
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


# -- Live Vision (camera) endpoints --------------------------------------
@app.get("/camera/mjpeg")
def camera_mjpeg():
    """Multipart JPEG stream for the Live Vision UI feed."""
    return StreamingResponse(
        _agent.camera.mjpeg(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/camera/frame")
def camera_frame():
    """Single JPEG snapshot of the latest annotated frame."""
    from fastapi.responses import Response

    data = _agent.camera.get_frame_jpeg()
    return Response(content=data, media_type="image/jpeg")


@app.get("/camera/occupancy/{lot_id}")
def camera_occupancy(lot_id: str):
    readings, frame_size = _agent.camera.get_occupancy(lot_id)
    return {
        "lot_id": lot_id,
        "frame_size": frame_size,
        "camera_available": _agent.camera.available,
        "occupancy": readings,
    }


# -- Calibration endpoints -----------------------------------------------
@app.post("/calibrate/grid-suggest")
def calibrate_grid_suggest(req: GridSuggestRequest):
    w = req.width or _agent.camera.frame_size[0]
    h = req.height or _agent.camera.frame_size[1]
    polys = suggest_grid(w, h, req.rows, req.cols, req.margin)
    slots = [
        {"slot_id": i + 1, "polygon": p} for i, p in enumerate(polys)
    ]
    return {"slots": slots}


@app.post("/calibrate/save")
def calibrate_save(req: SaveSlotsRequest):
    slots = [SlotROI(slot_id=int(s["slot_id"]), polygon=s["polygon"]) for s in req.slots]
    _agent.store.save_slots(req.lot_id, slots)
    # Refresh the camera loop's view of this lot on next frame.
    return {"saved": len(slots), "lot_id": req.lot_id}


@app.post("/calibrate/set-polygon")
def calibrate_set_polygon(req: SetPolygonRequest):
    _agent.store.set_slot_polygon(req.lot_id, req.slot_id, req.polygon)
    return {"ok": True, "lot_id": req.lot_id, "slot_id": req.slot_id}


def _main():
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=AGENT_PORT)  # CV agent is a localhost-only dev server


if __name__ == "__main__":
    _main()
