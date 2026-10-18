"""Apply a supplied binary logit temperature without changing candidate order."""

import json
import math
from pathlib import Path


def load_temperature(path: Path) -> float:
    # Sample IDs, labels and original scores stay in the artifact for audit only.
    document = json.loads(path.read_bytes())
    value = document.get("temperature") if isinstance(document, dict) else None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Calibration temperature must be a number")
    temperature = float(value)
    calibrated([0.5, 0.5], temperature)
    return temperature


def calibrated(probabilities: list[float], temperature: float) -> list[float]:
    if not math.isfinite(temperature) or temperature <= 0:
        raise ValueError("Calibration temperature must be finite and positive")
    p = min(max(probabilities[1], 1e-7), 1 - 1e-7)
    z = (math.log(p) - math.log1p(-p)) / temperature
    adjusted = 1 / (1 + math.exp(-z)) if z >= 0 else math.exp(z) / (1 + math.exp(z))
    return [1 - adjusted, adjusted]
