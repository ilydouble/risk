"""Apply a supplied binary logit temperature without changing candidate order."""

import math


def calibrated(probabilities: list[float], temperature: float) -> list[float]:
    if not math.isfinite(temperature) or temperature <= 0:
        raise ValueError("Calibration temperature must be finite and positive")
    p = min(max(probabilities[1], 1e-7), 1 - 1e-7)
    z = (math.log(p) - math.log1p(-p)) / temperature
    adjusted = 1 / (1 + math.exp(-z)) if z >= 0 else math.exp(z) / (1 + math.exp(z))
    return [1 - adjusted, adjusted]
