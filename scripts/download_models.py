#!/usr/bin/env python3
import os, urllib.request, sys
BASE = os.getenv("PRAGMA_MODEL_RELEASE", "https://github.com/AshutoshGitMirror/pragmapark/releases/download/v2.0.0")
DIR = os.getenv("MODEL_ARTIFACT_PATH", "src/models/artifacts")
os.makedirs(DIR, exist_ok=True)
for name in ("rf", "xgb", "meta"):
    path = os.path.join(DIR, f"{name}_model.joblib")
    if not os.path.exists(path):
        urllib.request.urlretrieve(f"{BASE}/{name}_model.joblib", path)  # ponytail: one-liner download, no retry/logging ceremony
