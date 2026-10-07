"""Portable node_edge state around the research model's forward implementation."""

import numpy as np
import torch
from riskgnn.gnn import RiskGNN
from torch import nn
from torch.nn import functional as F


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
        # Research callers keep their existing attributes; only the service persists them.
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
        # The v1 portable format contains only the node_edge path and classifier.
        return {name: value for name, value in state.items() if not self._inactive(name)}

    def load_state_dict(self, state_dict, strict=True, assign=False):
        state = {
            name: value for name, value in super().state_dict().items() if self._inactive(name)
        }
        state.update(state_dict)
        return super().load_state_dict(state, strict=strict, assign=assign)
