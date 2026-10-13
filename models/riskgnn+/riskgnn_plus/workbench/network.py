"""Share learned parameters while executing each isolated graph with local identities."""

import numpy as np
import torch
from torch import nn
from torch.func import functional_call

from riskgnn_plus.model import RiskGNNPlus, RiskGNNPlusOutput


def create_core(meta: dict, companies: np.ndarray, persons: np.ndarray, *, has_edges=True):
    return RiskGNNPlus(
        input_dim=16,
        output_dim=12,
        company_num=len(companies),
        person_num=len(persons),
        rel_num=len(meta["relations"]),
        cause_type_num=11,
        court_type_num=4,
        category_num=4,
        device=torch.device("cpu"),
        com_initial_emb=companies,
        person_initial_emb=persons,
        n_company_attr_dims=len(meta["features"]),
        use_hypergraph=True,
        use_edgegraph=has_edges,
        hyper_impl="vectorized",
        hete_scalar_weights=True,
        use_community_prior=False,
    )


class PortablePlus(nn.Module):
    def __init__(self, meta: dict, context: dict, events: dict):
        super().__init__()
        self.meta, self.context, self.events = meta, context, events
        # Graph-size-dependent embeddings are fixed inputs in context.npz, not learned weights.
        self.core = create_core(meta, np.zeros((1, 32)), np.zeros((0, 32)))
        self.graphs: dict[str, tuple] = {}

    def graph(self, snapshot: str):
        if snapshot in self.graphs:
            return self.graphs[snapshot]
        context = self.context
        companies = np.where(
            (context["snapshots"] == snapshot)
            & (np.arange(len(context["features"])) < self.meta["companyCount"])
        )[0]
        persons = np.where(
            (context["snapshots"] == snapshot)
            & (np.arange(len(context["features"])) >= self.meta["companyCount"])
        )[0]
        nodes = np.concatenate((companies, persons))
        local = {int(node): i for i, node in enumerate(nodes)}
        edge_mask = np.array(
            [int(row[0]) in local and int(row[1]) in local for row in context["edges"]], dtype=bool
        )
        source = context["edges"][edge_mask]
        edges = [[local[int(row[0])], local[int(row[1])]] for row in source]
        graph = (
            np.array(edges, dtype=np.int64).reshape(-1, 2),
            source[:, 2],
            context.get("weights", np.ones(len(context["edges"])))[edge_mask],
        )
        hypers = []
        for i in range(3):
            raw_nodes, raw_groups = context[f"hyper_nodes_{i}"], context[f"hyper_groups_{i}"]
            incidences = [
                (local[int(n)], int(g))
                for n, g in zip(raw_nodes, raw_groups, strict=True)
                if int(n) in local
            ]
            group_index = {g: j for j, g in enumerate(sorted({g for _, g in incidences}))}
            hypers.append(
                (
                    torch.tensor([n for n, _ in incidences], dtype=torch.long),
                    torch.tensor([group_index[g] for _, g in incidences], dtype=torch.long),
                    len(group_index),
                )
            )
        risk = {
            local[int(node)]: value for node, value in self.events.items() if int(node) in local
        }
        network = create_core(
            self.meta,
            context["company_embedding"][companies],
            context["person_embedding"][persons - self.meta["companyCount"]],
            has_edges=bool(len(edges)),
        )
        self.graphs[snapshot] = network, companies, local, graph, hypers, risk
        return self.graphs[snapshot]

    def forward(self, targets: list[int]) -> RiskGNNPlusOutput:
        if not targets:
            raise ValueError("At least one target is required")
        snapshots = {str(self.context["snapshots"][node]) for node in targets}
        if len(snapshots) != 1:
            raise ValueError("Forward targets must belong to one isolated snapshot")
        network, companies, local, graph, hypers, risk = self.graph(snapshots.pop())
        network.train(self.training)
        state = {**dict(self.core.named_parameters()), **dict(self.core.named_buffers())}
        # functional_call routes gradients and running statistics to the one portable state.
        result = functional_call(
            network,
            state,
            (
                risk,
                self.context["features"][companies],
                graph,
                hypers,
                list(range(len(companies))),
            ),
            strict=True,
        )
        selection = [local[node] for node in targets]
        return RiskGNNPlusOutput(*(value[selection] for value in result))
