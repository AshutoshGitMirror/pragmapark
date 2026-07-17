"""Offline unit tests for the CV module.

These exercise only the pure-Python parts (geometry + ultrasonic
adapters + the detector's class map). They deliberately avoid
torch / cv2 / PIL / requests so they run on a clean interpreter
and in CI without the heavy vision deps.
"""

import json
import os
import tempfile
from typing import List

import pytest

from src.cv.roi import (
    RoiStore,
    SlotROI,
    bbox_iou,
    map_boxes_to_slots,
    point_in_polygon,
    suggest_grid,
)
from src.cv.ultrasonic import (
    FileUltrasonicSource,
    SimulatedUltrasonicSource,
)
from src.cv.detector import VEHICLE_CLASSES


SQUARE = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]


def test_point_in_polygon_inside():
    assert point_in_polygon(5.0, 5.0, SQUARE) is True


def test_point_in_polygon_outside():
    assert point_in_polygon(15.0, 5.0, SQUARE) is False


def test_point_in_polygon_degenerate():
    assert point_in_polygon(1.0, 1.0, [[0.0, 0.0], [1.0, 1.0]]) is False


def test_bbox_iou_identical():
    box = [0.0, 0.0, 10.0, 10.0]
    assert bbox_iou(box, box) == pytest.approx(1.0)


def test_bbox_iou_disjoint():
    a = [0.0, 0.0, 1.0, 1.0]
    b = [5.0, 5.0, 6.0, 6.0]
    assert bbox_iou(a, b) == 0.0


def test_bbox_iou_partial():
    a = [0.0, 0.0, 2.0, 2.0]
    b = [1.0, 1.0, 3.0, 3.0]
    # overlap 1x1, union 7 -> 1/7
    assert bbox_iou(a, b) == pytest.approx(1.0 / 7.0)


def test_map_boxes_centroid_inside():
    slots = [SlotROI(slot_id=1, polygon=SQUARE)]
    boxes = [[2.0, 2.0, 4.0, 4.0]]  # centroid (3,3) inside
    occ = map_boxes_to_slots(boxes, slots)
    assert occ[1] is True


def test_map_boxes_iou_overlap():
    # Centroid (10.1, 5.0) is OUTSIDE the 10x10 square, but the box
    # overlaps the square's bbox with IoU ~0.06, so the IoU branch
    # (not the centroid branch) must flag the slot occupied.
    slots = [SlotROI(slot_id=1, polygon=SQUARE)]
    boxes = [[9.2, 1.0, 11.0, 9.0]]
    occ = map_boxes_to_slots(boxes, slots, iou_threshold=0.05)
    assert occ[1] is True


def test_map_boxes_empty_all_free():
    slots = [SlotROI(slot_id=1, polygon=SQUARE), SlotROI(slot_id=2, polygon=SQUARE)]
    occ = map_boxes_to_slots([], slots)
    assert occ == {1: False, 2: False}


def test_suggest_grid_count_and_bounds():
    polys = suggest_grid(100, 100, rows=4, cols=5, margin=0.1)
    assert len(polys) == 20
    for p in polys:
        xs = [c[0] for c in p]
        ys = [c[1] for c in p]
        assert min(xs) >= 10.0 - 1e-6  # 10% margin
        assert max(xs) <= 90.0 + 1e-6
        assert min(ys) >= 10.0 - 1e-6
        assert max(ys) <= 90.0 + 1e-6


def test_suggest_grid_invalid():
    with pytest.raises(ValueError):
        suggest_grid(100, 100, rows=0, cols=2)


def _tmp_store() -> RoiStore:
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.remove(path)
    return RoiStore(path=path)


def test_roistore_roundtrip():
    store = _tmp_store()
    slots = [SlotROI(slot_id=1, polygon=SQUARE), SlotROI(slot_id=2, polygon=SQUARE)]
    store.save_slots("A1", slots)
    got = store.get_slots("A1")
    assert len(got) == 2
    assert got[0].slot_id == 1
    assert got[0].polygon == SQUARE


def test_roistore_set_polygon_updates_and_adds():
    store = _tmp_store()
    store.set_slot_polygon("A1", 1, SQUARE)
    store.set_slot_polygon("A1", 2, [[20.0, 20.0], [30.0, 20.0], [30.0, 30.0], [20.0, 30.0]])
    store.set_slot_polygon("A1", 1, [[1.0, 1.0], [2.0, 1.0], [2.0, 2.0], [1.0, 2.0]])
    got = store.get_slots("A1")
    assert len(got) == 2
    assert got[0].polygon == [[1.0, 1.0], [2.0, 1.0], [2.0, 2.0], [1.0, 2.0]]


def test_simulated_ultrasonic_shape_and_determinism():
    src = SimulatedUltrasonicSource(seed=42, base_rate=0.5)
    out1 = src.read(8)
    assert len(out1) == 8
    assert all(isinstance(v, bool) for v in out1)
    out2 = SimulatedUltrasonicSource(seed=42, base_rate=0.5).read(8)
    assert out1 == out2  # deterministic for same seed


def test_file_ultrasonic_json():
    fd, path = tempfile.mkstemp(suffix=".json")
    os.write(fd, json.dumps({"slots": [True, False, True]}).encode())
    os.close(fd)
    src = FileUltrasonicSource(path)
    assert src.read(3) == [True, False, True]
    # Padding when slot count is larger.
    assert src.read(5) == [True, False, True, False, False]


def test_file_ultrasonic_csv():
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.write(fd, b"1,0,1,1")
    os.close(fd)
    src = FileUltrasonicSource(path)
    assert src.read(4) == [True, False, True, True]


def test_file_ultrasonic_missing_raises():
    with pytest.raises(FileNotFoundError):
        FileUltrasonicSource("/nonexistent/path.json").read(1)


def test_vehicle_classes_map():
    # COCO: car=2, motorcycle=3, bus=5, truck=7
    assert VEHICLE_CLASSES == {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
