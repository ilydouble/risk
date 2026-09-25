#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${COMRISK_PYTHON:-.venv/bin/python}"
"$PYTHON" scripts/fetch_smesd.py
"$PYTHON" -m comrisk.smesd
"$PYTHON" -m pytest -q
"$PYTHON" -m comrisk.benchmark --epochs 80 --seeds 42 43 44
