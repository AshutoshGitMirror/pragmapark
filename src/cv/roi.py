"""Slot ROI geometry: load/save per-lot slot polygons and map vehicle
detections onto them. Pure-Python (no torch / no cv2) so it is
unit-testable offline.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# A polygon is a list of [x, y] corners in image pixel coordinates.
Polygon = List[List[float]]
Box = List[float]  # [x1, y1, x2, y2]


@dataclass
class SlotROI:
    """One parking slot: a stable slot_id plus its polygon outline."""

    slot_id: int
    polygon: Polygon


def _config_dir() -> str:
    env = os.environ.get("PRAGMA_CONFIG_DIR")
    if env:
        return env
    # Default: <project root>/config  (gitignored, camera-calibration data)
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(here, "config")


def _roi_path() -> str:
    return os.path.join(_config_dir(), "lot_rois.json")


def point_in_polygon(x: float, y: float, polygon: Polygon) -> bool:
    """Ray-casting point-in-polygon test."""
    inside = False
    n = len(polygon)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i][0], polygon[i][1]
        xj, yj = polygon[j][0], polygon[j][1]
        intersects = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def _polygon_bbox(polygon: Polygon) -> Box:
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return [min(xs), min(ys), max(xs), max(ys)]


def bbox_iou(a: Box, b: Box) -> float:
    """Intersection-over-Union of two [x1,y1,x2,y2] boxes."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0.0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    if union <= 0.0:
        return 0.0
    return inter / union


def map_boxes_to_slots(
    boxes: List[Box],
    slots: List[SlotROI],
    iou_threshold: float = 0.1,
) -> Dict[int, bool]:
    """Return {slot_id: occupied} by testing each vehicle box against each
    slot polygon: a slot is occupied if any box's centroid falls inside
    the polygon OR the box overlaps the slot's bounding box above the
    IoU threshold.
    """
    result: Dict[int, bool] = {s.slot_id: False for s in slots}
    for slot in slots:
        sbbox = _polygon_bbox(slot.polygon)
        for box in boxes:
            cx = (box[0] + box[2]) / 2.0
            cy = (box[1] + box[3]) / 2.0
            if point_in_polygon(cx, cy, slot.polygon):
                result[slot.slot_id] = True
                break
            if bbox_iou(box, sbbox) >= iou_threshold:
                result[slot.slot_id] = True
                break
    return result


def suggest_grid(
    width: int,
    height: int,
    rows: int,
    cols: int,
    margin: float = 0.05,
) -> List[Polygon]:
    """Propose a regular rows x cols slot grid as calibration starting
    point. Pure math (no cv2 needed). Each cell becomes a rectangle
    polygon; the operator nudges corners in the Live Vision UI.
    """
    if rows < 1 or cols < 1:
        raise ValueError("rows and cols must be >= 1")
    mx = width * margin
    my = height * margin
    usable_w = width - 2 * mx
    usable_h = height - 2 * my
    cw = usable_w / cols
    ch = usable_h / rows
    polys: List[Polygon] = []
    for r in range(rows):
        for c in range(cols):
            x0 = mx + c * cw
            y0 = my + r * ch
            polys.append(
                [
                    [x0, y0],
                    [x0 + cw, y0],
                    [x0 + cw, y0 + ch],
                    [x0, y0 + ch],
                ]
            )
    return polys


class RoiStore:
    """Loads / saves per-lot slot ROI polygons from a local JSON file.

    The file lives under the (gitignored) config dir because it is
    camera-calibration data specific to one physical installation.
    """

    def __init__(self, path: Optional[str] = None):
        self.path = path or _roi_path()

    def _load_all(self) -> dict:
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_all(self, data: dict) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    def list_lots(self) -> List[str]:
        return sorted(self._load_all().keys())

    def get_slots(self, lot_id: str) -> List[SlotROI]:
        data = self._load_all()
        raw = data.get(lot_id, [])
        return [SlotROI(slot_id=int(s["slot_id"]), polygon=s["polygon"]) for s in raw]

    def save_slots(self, lot_id: str, slots: List[SlotROI]) -> None:
        data = self._load_all()
        data[lot_id] = [
            {"slot_id": s.slot_id, "polygon": s.polygon} for s in slots
        ]
        self._save_all(data)

    def set_slot_polygon(self, lot_id: str, slot_id: int, polygon: Polygon) -> None:
        slots = self.get_slots(lot_id)
        found = False
        for s in slots:
            if s.slot_id == slot_id:
                s.polygon = polygon
                found = True
                break
        if not found:
            slots.append(SlotROI(slot_id=slot_id, polygon=polygon))
        self.save_slots(lot_id, slots)
