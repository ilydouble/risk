"""Independent graph-bound RiskGNN+ reload and uncertainty diagnostics."""

from pathlib import Path

import numpy as np
import torch

from riskgnn.workbench.artifacts import read_json, verify
from riskgnn_plus.workbench.adaptive import ADAPTIVE_ARCHITECTURE
from riskgnn_plus.workbench.network import PortablePlus
from riskgnn_plus.workbench.preparation import ARCHITECTURE, FORMAT


class PlusPredictor:
    def __init__(self, directory: Path):
        verify(directory, FORMAT)
        self.meta = read_json(directory / "metadata.json")
        if self.meta["architecture"] not in {ARCHITECTURE, ADAPTIVE_ARCHITECTURE}:
            raise ValueError("Unsupported RiskGNN+ architecture")
        self.ids = read_json(directory / "ids.json")
        self.index = {name: i for i, name in enumerate(self.ids[: self.meta["companyCount"]])}
        self.context = dict(np.load(directory / "context.npz", allow_pickle=False))
        self.model = PortablePlus(
            self.meta, self.context, read_json(directory / "risk_events.json")
        )
        self.model.load_state_dict(
            torch.load(directory / "weights.pt", map_location="cpu", weights_only=True)
        )
        self.model.eval()

    def predict(self, ids: list[str]) -> list[dict]:
        missing = [name for name in ids if name not in self.index]
        if missing:
            raise KeyError(f"Unknown bound-graph enterprise: {missing[0]}")
        grouped: dict[str, list[int]] = {}
        for name in ids:
            node = self.index[name]
            grouped.setdefault(str(self.context["snapshots"][node]), []).append(node)
        rows = {}
        with torch.inference_mode():
            for nodes in grouped.values():
                result = self.model(nodes)
                for i, node in enumerate(nodes):
                    probability = float(result.probabilities[i, 1])
                    rows[node] = {
                        "companyId": self.ids[node],
                        "probability": probability,
                        "predictedLabel": int(probability >= 0.5),
                        "fusedProbability": float(result.fused_probabilities[i, 1]),
                        "uncertainty": float(result.fused_uncertainty[i]),
                        "conflict": float(result.conflict[i]),
                        "nodeProbability": float(result.node_probabilities[i, 1]),
                        "graphProbability": float(result.graph_probabilities[i, 1]),
                    }
        return [rows[self.index[name]] for name in ids]
