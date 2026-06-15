#!/usr/bin/env python3
"""Download trained ML models from GitHub releases during Render build.

Called from render.yaml buildCommand so models are baked into the deploy
artifact, avoiding runtime download timeout on free tier (512MB)."""
import os
import sys
import urllib.request
import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("download_models")

RELEASE_BASE = os.getenv(
    "PRAGMA_MODEL_RELEASE",
    "https://github.com/AshutoshGitMirror/pragmapark/releases/download/v2.0.0",
)
MODEL_DIR = os.getenv("MODEL_ARTIFACT_PATH", "src/models/artifacts")
MODELS = ["rf", "xgb", "meta"]


def main() -> None:
    os.makedirs(MODEL_DIR, exist_ok=True)
    for name in MODELS:
        path = os.path.join(MODEL_DIR, f"{name}_model.joblib")
        if os.path.exists(path):
            logger.info("  [SKIP] %s already exists at %s", name, path)
            continue
        url = f"{RELEASE_BASE}/{name}_model.joblib"
        logger.info("  [DOWNLOAD] %s from %s ...", name, url)
        try:
            urllib.request.urlretrieve(url, path)
            size_mb = os.path.getsize(path) / (1024 * 1024)
            logger.info("  [OK] %s (%.1f MB)", name, size_mb)
        except Exception as e:
            logger.error("  [FAIL] %s: %s", name, e)
            sys.exit(1)
    logger.info("All models downloaded to %s", MODEL_DIR)


if __name__ == "__main__":
    main()
