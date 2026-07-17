"""Command-line runner for the CV agent.

Modes::

    # One image, detect only (no push)
    python -m src.cv.cli --mode file --lot-id A1 --image shot.jpg

    # One image, detect AND push real vision to Render
    python -m src.cv.cli --mode file --lot-id A1 --image shot.jpg --push

    # Live webcam loop (cv2)
    python -m src.cv.cli --mode live --lot-id A1 --camera 0 --push

    # Offline eval against a labelled dataset dir (optional; PKLot not required)
    python -m src.cv.cli --mode eval --lot-id A1 --dataset-dir ./eval/A1

    # Seed an initial slot grid for UI-assisted calibration
    python -m src.cv.cli --mode calibrate --lot-id A1 --rows 5 --cols 10 --width 1280 --height 720

Heavy deps (torch, cv2, PIL, requests) are imported lazily so this
module and the geometry unit tests run on a clean interpreter.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from typing import List, Optional

from .detector import DEFAULT_MODEL, Detector
from .roi import RoiStore, SlotROI, suggest_grid
from .ultrasonic import FileUltrasonicSource, SimulatedUltrasonicSource


def _b64_of(path: str) -> str:
    with open(path, "rb") as fh:
        return base64.urlsafe_b64encode(fh.read()).decode("ascii")


def _load_image(path: str):
    # Lazy import so a torch-less env can still import the CLI.
    import numpy as np
    from PIL import Image

    img = Image.open(path).convert("RGB")
    return np.asarray(img)


def run_file(lot_id: str, image: str, push: bool, model: str,
              ultrasonic: Optional[str], iou: float,
              sensor_key: Optional[str] = None) -> dict:
    det = Detector(model_path=model)
    store = RoiStore()
    slots = store.get_slots(lot_id)
    if not slots:
        return {"error": f"No ROIs for lot '{lot_id}'. Run --mode calibrate first."}
    boxes = det.detect(_load_image(image))
    from .roi import map_boxes_to_slots

    occ = map_boxes_to_slots(boxes, slots, iou_threshold=iou)
    out = {
        "lot_id": lot_id,
        "boxes": boxes,
        "occupancy": {str(k): bool(v) for k, v in occ.items()},
    }
    if push:
        from .agent import Agent

        src = FileUltrasonicSource(ultrasonic) if ultrasonic else None
        agent = Agent(model_path=model, store=store, sensor_key=sensor_key, lot_id=lot_id)
        payload = agent.push(lot_id, _load_image(image), src, iou)
        out["push"] = payload
    return out


def run_live(lot_id: str, camera: int, push: bool, model: str,
              interval: float, iou: float) -> None:
    import cv2

    import numpy as np

    det = Detector(model_path=model)
    store = RoiStore()
    slots = store.get_slots(lot_id)
    if not slots:
        print(f"No ROIs for lot '{lot_id}'. Run --mode calibrate first.")
        return
    cap = cv2.VideoCapture(camera)
    if not cap.isOpened():
        print(f"Cannot open camera {camera}.")
        return
    print(f"Live loop on camera {camera} (Ctrl-C to stop)...")
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            boxes = det.detect(frame)
            from .roi import map_boxes_to_slots

            occ = map_boxes_to_slots(boxes, slots, iou_threshold=iou)
            # Draw boxes for operator feedback.
            for b in boxes:
                x1, y1, x2, y2 = (int(v) for v in b)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 0), 2)
            cv2.imshow("pragma-cv", frame)
            if push:
                from .agent import Agent

                agent = Agent(model_path=model, store=store)
                agent.push(lot_id, frame, None, iou)
                print(f"pushed; occupied={sum(occ.values())}/{len(slots)}")
            if cv2.waitKey(int(interval * 1000)) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


def run_eval(lot_id: str, dataset_dir: str, model: str, iou: float) -> dict:
    """Evaluate detection->slot mapping against a labelled dataset.

    Expected layout: ``dataset_dir/*.jpg`` plus ``<name>.json`` with
    ``{"slot_id": bool}`` ground truth per image. Reports per-slot
    accuracy (no external dataset required — supply your own).
    """
    import os

    det = Detector(model_path=model)
    store = RoiStore()
    slots = store.get_slots(lot_id)
    if not slots:
        return {"error": f"No ROIs for lot '{lot_id}'."}
    correct = 0
    total = 0
    for name in sorted(os.listdir(dataset_dir)):
        if not name.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        base = os.path.splitext(name)[0]
        gt_path = os.path.join(dataset_dir, base + ".json")
        if not os.path.exists(gt_path):
            continue
        with open(gt_path, "r", encoding="utf-8") as fh:
            gt = json.load(fh)
        boxes = det.detect(_load_image(os.path.join(dataset_dir, name)))
        from .roi import map_boxes_to_slots

        occ = map_boxes_to_slots(boxes, slots, iou_threshold=iou)
        for s in slots:
            key = str(s.slot_id)
            if key not in gt:
                continue
            total += 1
            if bool(occ.get(s.slot_id, False)) == bool(gt[key]):
                correct += 1
    return {"lot_id": lot_id, "evaluated": total, "accuracy": correct / total if total else None}


def run_calibrate(lot_id: str, rows: int, cols: int, width: int,
                  height: int, margin: float) -> dict:
    store = RoiStore()
    polys = suggest_grid(width, height, rows, cols, margin)
    slots = [SlotROI(slot_id=i + 1, polygon=p) for i, p in enumerate(polys)]
    store.save_slots(lot_id, slots)
    return {
        "lot_id": lot_id,
        "slots_saved": len(slots),
        "note": "Grid is a starting point; fine-tune corners in the Live Vision UI.",
        "path": store.path,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Pragma CV agent runner")
    p.add_argument("--mode", choices=["file", "live", "eval", "calibrate"], required=True)
    p.add_argument("--lot-id", required=True)
    p.add_argument("--image")
    p.add_argument("--camera", type=int, default=0)
    p.add_argument("--dataset-dir")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--ultrasonic-source")
    p.add_argument("--iou", type=float, default=0.1)
    p.add_argument("--interval", type=float, default=2.0)
    p.add_argument("--rows", type=int, default=5)
    p.add_argument("--cols", type=int, default=10)
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=720)
    p.add_argument("--margin", type=float, default=0.05)
    p.add_argument("--push", action="store_true")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.mode == "file":
        if not args.image:
            print("--image required for file mode")
            return 2
        print(json.dumps(run_file(args.lot_id, args.image, args.push, args.model,
                                args.ultrasonic_source, args.iou), indent=2))
    elif args.mode == "live":
        run_live(args.lot_id, args.camera, args.push, args.model, args.interval, args.iou)
    elif args.mode == "eval":
        if not args.dataset_dir:
            print("--dataset-dir required for eval mode")
            return 2
        print(json.dumps(run_eval(args.lot_id, args.dataset_dir, args.model, args.iou), indent=2))
    elif args.mode == "calibrate":
        print(json.dumps(run_calibrate(args.lot_id, args.rows, args.cols,
                                     args.width, args.height, args.margin), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
