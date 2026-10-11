from pathlib import Path

import numpy as np
import torch

from riskgnn.workbench.artifacts import read_json, verify
from riskgnn.workbench.network import create_model
from riskgnn.workbench.sampling import Sampler, forward


class Predictor:
    def __init__(self, directory: Path):
        verify(directory, "riskgnn-model-v2")
        self.meta = read_json(directory / "metadata.json")
        self.ids = read_json(directory / "ids.json")
        companies = self.ids[: self.meta.get("companyCount", len(self.ids))]
        self.index = {name: i for i, name in enumerate(companies)}
        self.context = dict(np.load(directory / "context.npz", allow_pickle=False))
        self.features = torch.tensor(self.context["features"])
        self.sampler = Sampler(
            self.context["edges"],
            len(self.ids),
            self.context.get("weights"),
            self.context.get("confidence"),
        )
        self.model = create_model(self.meta, len(self.ids))
        self.model.load_state_dict(
            torch.load(directory / "weights.pt", map_location="cpu", weights_only=True)
        )
        self.model.eval()

    def predict(self, ids: list[str]) -> list[dict]:
        missing = [name for name in ids if name not in self.index]
        if missing:
            raise KeyError(f"Unknown bound-graph enterprise: {missing[0]}")
        result = []
        with torch.inference_mode():
            for name in ids:
                node = self.index[name]
                # Per-target deterministic neighborhoods keep predictions independent of
                # request order and batch companions, including export/reload verification.
                predicted = forward(self.model, self.features, self.sampler, [node], node + 999999)
                probability = float(predicted[0, 1].exp())
                result.append(
                    {
                        "companyId": name,
                        "probability": probability,
                        "predictedLabel": int(probability >= 0.5),
                    }
                )
        return result
