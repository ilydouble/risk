from pathlib import Path

import numpy as np
import torch

from service.files import read_json, verify
from service.model.network import EdgeRiskGNN
from service.model.sampling import Sampler


class Predictor:
    def __init__(self, directory: Path):
        verify(directory, "riskgnn-model-v1")
        self.meta = read_json(directory / "metadata.json")
        if self.meta.get("architecture") != "sg-node-edge-v1":
            raise ValueError("Unsupported model architecture")
        self.ids = read_json(directory / "ids.json")
        self.index = {name: i for i, name in enumerate(self.ids)}
        self.context = dict(np.load(directory / "context.npz", allow_pickle=False))
        self.features = torch.tensor(self.context["features"])
        self.sampler = Sampler(self.context["edges"], len(self.ids))
        self.model = EdgeRiskGNN(len(self.ids), len(self.meta["relations"]))
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
                n, edges, types = self.sampler.sample([node], node + 999999)
                probability = float(self.model(self.features, n, edges, types, 1)[0, 1].exp())
                result.append(
                    {
                        "companyId": name,
                        "probability": probability,
                        "predictedLabel": int(probability >= 0.5),
                    }
                )
        return result
