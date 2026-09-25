#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
uv run python scripts/fetch_smesd.py
uv run python -m risk_api.modules.benchmark.engine.smesd
uv run pytest -q tests/test_model.py tests/test_benchmark_api.py
uv run python -m risk_api.modules.benchmark.engine.benchmark --epochs 80 --seeds 42 43 44
