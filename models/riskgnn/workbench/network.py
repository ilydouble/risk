"""Portable node_edge state around the research model's forward implementation."""

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from riskgnn.gnn import RiskGNN


class EdgeRiskGNN(RiskGNN):
    def __init__(self, nodes: int, relations: int, features: int = 6, seed: int = 0):
        super().__init__(
            input_dim=32,
            output_dim=32,
            company_num=nodes,
            person_num=0,
            rel_num=relations,
            cause_type_num=11,
            device=torch.device("cpu"),
            com_initial_emb=np.random.RandomState(seed).normal(0, 0.1, size=(nodes, 32)),
            person_initial_emb=np.zeros((0, 32)),
            use_hypergraph=False,
            use_edgegraph=True,
            n_company_attr_dims=features,
            hyper_impl="vectorized",
            hete_scalar_weights=False,
        )
        # Research callers keep their existing attributes; the workbench CLI persists them.
        for name in ("company_emb", "alpha"):
            value = getattr(self, name)
            delattr(self, name)
            self.register_buffer(name, value)
        self.classifier = nn.Linear(32, 2)

    def forward(self, features, nodes, edges, types, count):
        encoded = super().forward_batch(
            features, edges, types, torch.ones(len(edges)), nodes, count
        )
        return F.log_softmax(self.classifier(encoded), dim=-1)

    @staticmethod
    def _inactive(name: str) -> bool:
        return name.startswith(("riskinfo.", "hypergnn."))

    def state_dict(self, *args, **kwargs):
        state = super().state_dict(*args, **kwargs)
        # The portable model format contains only the node_edge path and classifier.
        return {name: value for name, value in state.items() if not self._inactive(name)}

    def load_state_dict(self, state_dict, strict=True, assign=False):
        state = {
            name: value for name, value in super().state_dict().items() if self._inactive(name)
        }
        state.update(state_dict)
        return super().load_state_dict(state, strict=strict, assign=assign)


class DatasetRiskGNN(EdgeRiskGNN):
    """Snapshot node_edge profile using original RiskGNN layers and typed context."""

    def __init__(self, companies: int, persons: int, relations: int, features: int):
        RiskGNN.__init__(
            self,
            input_dim=32,
            output_dim=32,
            company_num=companies,
            person_num=persons,
            rel_num=relations,
            cause_type_num=11,
            device=torch.device("cpu"),
            com_initial_emb=np.random.RandomState(0).normal(0, 0.1, size=(companies, 32)),
            person_initial_emb=np.random.RandomState(1).normal(0, 0.1, size=(persons, 32)),
            use_hypergraph=False,
            use_edgegraph=True,
            n_company_attr_dims=features,
            hyper_impl="vectorized",
            hete_scalar_weights=True,
        )
        for name in ("company_emb", "person_emb", "alpha"):
            value = getattr(self, name)
            delattr(self, name)
            self.register_buffer(name, value)
        self.classifier = nn.Linear(32, 2)

    def forward(self, features, nodes, edges, types, count, weights=None, confidence=None):
        if weights is None or confidence is None:
            raise ValueError("Snapshot profile requires explicit weight/confidence tensors")
        encoded = RiskGNN.forward_batch(
            self,
            features,
            edges,
            types,
            weights,
            nodes,
            count,
            edge_confidence_local=confidence,
        )
        return F.log_softmax(self.classifier(encoded), dim=-1)


def create_model(metadata: dict, nodes: int) -> EdgeRiskGNN:
    if metadata.get("architecture", "sg-node-edge-v2") == "sg-node-edge-v2":
        return EdgeRiskGNN(nodes, len(metadata["relations"]), features=len(metadata["features"]))
    if metadata["architecture"] == "dataset-node-edge-v1":
        return DatasetRiskGNN(
            metadata["companyCount"],
            metadata["personCount"],
            len(metadata["relations"]),
            len(metadata["features"]),
        )
    raise ValueError("Unsupported model architecture")
