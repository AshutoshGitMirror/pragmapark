#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD"
echo "[$(date)] Starting retrain pipeline..."
PYTHON="${VENV_PATH:-.venv}/bin/python"
if [ ! -f "$PYTHON" ]; then PYTHON=$(which python3); fi
echo "[$(date)] Starting retrain pipeline using $PYTHON..."
"$PYTHON" scripts/retrain.py
echo "[$(date)] Retrain done."
