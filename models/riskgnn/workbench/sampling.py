import numpy as np
import torch

from riskgnn.train_sg_neighbor import build_csr, sample_neighbors, to_batch_tensors


class Sampler:
    def __init__(self, edges: np.ndarray, nodes: int, weights=None, confidence=None):
        self.weighted = weights is not None
        self.confidence = (
            {tuple(row): float(value) for row, value in zip(edges, confidence, strict=True)}
            if confidence is not None
            else {}
        )
        self.csr = build_csr(
            # Research sampler traverses CSR rows as centers and emits neighbor -> center.
            # Reversing the lookup (not the output graph) preserves directed input semantics.
            torch.tensor(edges[:, [1, 0]].T if self.weighted else edges[:, :2].T),
            torch.tensor(edges[:, 2]),
            torch.tensor(weights) if weights is not None else torch.ones(len(edges)),
            nodes,
        )

    def sample(self, targets: list[int], seed: int, fanout: int = 2):
        n, edges, types, weights, _ = sample_neighbors(*self.csr, [fanout] * 5, targets, seed)
        nodes, edge_index, edge_type, _ = to_batch_tensors(
            n, edges, types, weights, torch.device("cpu")
        )
        return nodes, edge_index, edge_type

    def sample_graph(self, targets: list[int], seed: int, fanout: int = 2):
        n, edges, types, weights, _ = sample_neighbors(*self.csr, [fanout] * 5, targets, seed)
        nodes, edge_index, edge_type, edge_weights = to_batch_tensors(
            n, edges, types, weights, torch.device("cpu")
        )
        confidence = (
            torch.tensor(
                [
                    self.confidence[(int(n[a]), int(n[b]), int(t))]
                    for (a, b), t in zip(edge_index, edge_type, strict=True)
                ]
            )
            if self.weighted
            else torch.ones(len(edge_index))
        )
        return nodes, edge_index, edge_type, edge_weights, confidence


def forward(model, features, sampler, targets, seed):
    if sampler.weighted:
        n, edges, types, weights, confidence = sampler.sample_graph(targets, seed)
        return model(features, n, edges, types, len(targets), weights, confidence)
    n, edges, types = sampler.sample(targets, seed)
    return model(features, n, edges, types, len(targets))
