import os
import logging
import urllib.request
import joblib

logger = logging.getLogger(__name__)

RELEASE_BASE = "https://github.com/AshutoshGitMirror/pragmapark/releases/download/v1.0.0"


def ensure_model(name: str, model_dir: str) -> object | None:
    path = os.path.join(model_dir, f"{name}_model.joblib")
    if os.path.exists(path):
        try:
            return joblib.load(path)
        except Exception as e:
            logger.warning("Failed to load local %s: %s", path, e)
    if os.environ.get("PRAGMA_ENV") == "testing":
        return None
    url = f"{RELEASE_BASE}/{name}_model.joblib"
    os.makedirs(model_dir, exist_ok=True)
    try:
        logger.info("Downloading %s from %s ...", name, url)
        urllib.request.urlretrieve(url, path)  # nosec B310
        logger.info("Downloaded %s to %s", name, path)
        return joblib.load(path)
    except Exception as e:
        logger.warning("Failed to download %s: %s", name, e)
    return None
