import numpy as np
import torch
from riskgnn.train_sg_neighbor import build_csr, sample_neighbors, to_batch_tensors


class Sampler:
    def __init__(self, edges: np.ndarray, nodes: int):
        self.csr = build_csr(
            torch.tensor(edges[:, :2].T),
            torch.tensor(edges[:, 2]),
            torch.ones(len(edges)),
            nodes,
        )

    def sample(self, targets: list[int], seed: int, fanout: int = 2):
        n, edges, types, weights, _ = sample_neighbors(*self.csr, [fanout] * 5, targets, seed)
        nodes, edge_index, edge_type, _ = to_batch_tensors(
            n, edges, types, weights, torch.device("cpu")
        )
        return nodes, edge_index, edge_type
