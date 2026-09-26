#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
uv run python -m training.cli fetch
uv run python -m training.cli prepare
uv run pytest -q
uv run python -m training.cli benchmark --epochs 80 --seeds 42 43 44
