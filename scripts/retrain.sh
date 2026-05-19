#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD"
echo "[$(date)] Starting retrain pipeline..."
/tmp/pragma_venv/bin/python scripts/retrain.py
echo "[$(date)] Retrain done."
