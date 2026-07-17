"""Pragma local CV module.

This package is the locally-running Computer-Vision agent. It loads a
pretrained COCO YOLOv8 model, detects vehicles in a real camera
frame / image / video, and maps those detections onto per-lot slot
ROI polygons to produce REAL per-slot occupancy. It then pushes that
occupancy (``vision_readings``) to the Render backend's existing
ingestion endpoint.

Design invariants (see .opencode/plans/cv_module_plan.md):
  * torch / ultralytics are imported LAZILY inside functions so this
    package can be imported (and unit-tested for geometry) without
    torch installed.
  * The Render backend NEVER imports src.cv.* — this stays a
    separate process so Render's 512MB free tier is unaffected.
  * The ultrasonic leg is a pluggable interface whose bundled impl
    is a clearly-labelled SIMULATION (no hardware exists). The agent
    pushes real vision only; ultrasonic is an explicit "no hardware"
    placeholder when absent.
"""

from .roi import (
    SlotROI,
    RoiStore,
    point_in_polygon,
    bbox_iou,
    map_boxes_to_slots,
    suggest_grid,
)
from .ultrasonic import (
    UltrasonicSource,
    SimulatedUltrasonicSource,
    FileUltrasonicSource,
)

__all__ = [
    "SlotROI",
    "RoiStore",
    "point_in_polygon",
    "bbox_iou",
    "map_boxes_to_slots",
    "suggest_grid",
    "UltrasonicSource",
    "SimulatedUltrasonicSource",
    "FileUltrasonicSource",
]
