import json
from pathlib import Path

import torch

from .model import ComRisk
from .preprocessing import tensorize
from .prior import add_prior
from .schema import Dataset


class Predictor:
    def __init__(self, artifact):
        artifact = Path(artifact)
        self.meta = json.loads((artifact / "metadata.json").read_text())
        if self.meta["version"] != 2:
            raise ValueError("unsupported artifact version; retrain")
        self.model = ComRisk(**self.meta["config"])
        self.model.load_state_dict(
            torch.load(artifact / "weights.pt", map_location="cpu", weights_only=True)
        )
        self.model.eval()

    def predict(self, data: Dataset, ids=None):
        for key, value in self.meta["schema"].items():
            if getattr(data, key) != value:
                raise ValueError(f"schema mismatch: {key}")
        if data.target_description != self.meta["target_description"]:
            raise ValueError("target mismatch")
        known = {n.id for n in data.nodes if n.kind == "company"}
        if ids is not None and set(ids) - known:
            raise ValueError("unknown company IDs")
        graph = tensorize(data, self.meta["preprocessor"])
        if self.meta["prior"]:
            add_prior(graph, data, self.meta["prior"])
        with torch.no_grad():
            p = (
                (self.model(graph, self.meta["mode"]) + self.meta["calibration"]["intercept"])
                .sigmoid()
                .tolist()
            )
        rows = {
            n.id: {
                "company_id": n.id,
                "risk_probability": p[i],
                "credit_score": round(300 + 550 * (1 - p[i])),
                "score_mapping": "linear_demo_not_validated_credit_scale",
                "predicted_label": int(p[i] >= self.meta["threshold"]),
            }
            for i, n in enumerate(data.nodes)
            if n.kind == "company"
        }
        return {
            "model": self.meta["model"],
            "synthetic_training": self.meta["synthetic"],
            "synthetic_input": data.synthetic,
            "calibrated": True,
            "calibration_scope": "public benchmark validation",
            "target_description": self.meta["target_description"],
            "threshold": self.meta["threshold"],
            "predictions": [rows[i] for i in (list(rows) if ids is None else ids)],
        }
