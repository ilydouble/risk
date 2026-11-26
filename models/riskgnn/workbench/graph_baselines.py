"""Train ordinary graph baselines on the same isolated snapshots as RiskGNN+."""

from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from torch_geometric.nn import GCNConv, HGTConv, RGCNConv
from torch_geometric.utils import coalesce

from riskgnn.workbench.artifacts import read_json
from riskgnn.workbench.attribute_baselines import AttributeNetwork, train_boosted_trees


class GraphBaseline(nn.Module):
    def __init__(self, algorithm, metadata, context):
        super().__init__()
        self.algorithm = algorithm
        company = torch.arange(len(context["features"])) < metadata["companyCount"]
        edges = torch.as_tensor(context["edges"], dtype=torch.long)
        features = torch.as_tensor(context["features"], dtype=torch.float32)
        persons = torch.as_tensor(context["person_embedding"], dtype=torch.float32)
        relation_count = len(metadata["relations"])
        edge_types = (
            torch.stack((company[edges[:, 0]], edges[:, 2], company[edges[:, 1]]), dim=1)
            .unique(dim=0)
            .tolist()
            if algorithm == "hgt"
            else []
        )
        self.graphs = {}
        for snapshot in np.unique(context["snapshots"]):
            nodes = torch.from_numpy(np.flatnonzero(context["snapshots"] == snapshot))
            mapping = torch.full((len(company),), -1, dtype=torch.long)
            mapping[nodes] = torch.arange(len(nodes))
            keep = (mapping[edges[:, 0]] >= 0) & (mapping[edges[:, 1]] >= 0)
            edge = mapping[edges[keep, :2]].T.contiguous()
            kinds = edges[keep, 2]
            nc = int(company[nodes].sum())
            typed = {}
            for src, relation, dst in edge_types:
                mask = (kinds == relation) & ((edge[0] < nc) == src) & ((edge[1] < nc) == dst)
                typed[str(src), str(relation), str(dst)] = edge[:, mask] - torch.tensor(
                    [[0 if src else nc], [0 if dst else nc]]
                )
            self.graphs[str(snapshot)] = (
                mapping,
                features[nodes[:nc]],
                persons[nodes[nc:] - metadata["companyCount"]],
                coalesce(edge, num_nodes=len(nodes)) if algorithm == "gcn" else edge,
                kinds,
                typed,
            )
        self.projection = nn.ModuleDict(
            {
                "1": nn.Linear(features.shape[1], 64),
                "0": nn.Linear(persons.shape[1], 64),
            }
        )
        if algorithm == "gcn":
            self.layers = nn.ModuleList([GCNConv(64, 64), GCNConv(64, 2)])
        elif algorithm == "rgcn":
            self.layers = nn.ModuleList(
                [
                    RGCNConv(64, width, relation_count, num_bases=min(4, relation_count))
                    for width in (64, 2)
                ]
            )
        elif algorithm == "hgt":
            types = [(str(src), str(rel), str(dst)) for src, rel, dst in edge_types]
            if not types:
                raise ValueError("HGT requires ordinary relationship edges")
            self.layers = nn.ModuleList(
                [HGTConv(64, 64, (["1", "0"], types), heads=4) for _ in range(2)]
            )
            self.classifier = nn.Linear(64, 2)
        else:
            raise ValueError(f"Unsupported graph baseline: {algorithm}")

    def activate(self, x):
        return F.dropout(F.relu(x), p=0.2, training=self.training)

    def forward(self, snapshot, targets):
        mapping, companies, persons, edges, kinds, typed = self.graphs[snapshot]
        inputs = {
            "1": self.activate(self.projection["1"](companies)),
            "0": self.activate(self.projection["0"](persons)),
        }
        if self.algorithm == "hgt":
            for layer in self.layers:
                updated = layer(inputs, typed)
                inputs = {
                    k: self.activate(updated.get(k) if updated.get(k) is not None else value)
                    for k, value in inputs.items()
                }
            return self.classifier(inputs["1"][mapping[targets]])
        x = torch.cat((inputs["1"], inputs["0"]))
        relation_args = (kinds,) if self.algorithm == "rgcn" else ()
        x = self.activate(self.layers[0](x, edges, *relation_args))
        return self.layers[1](x, edges, *relation_args)[mapping[targets]]


def baseline_network(algorithm, meta, context):
    if algorithm in {"lr", "mlp"}:
        return AttributeNetwork(algorithm, context)
    return GraphBaseline(algorithm, meta, context)


def train_baseline(algorithm, prepared: Path, output: Path, epochs: int, callback):
    meta = read_json(prepared / "metadata.json")
    with np.load(prepared / "context.npz", allow_pickle=False) as data:
        context = dict(data)
    torch.manual_seed(meta["seed"])
    torch.use_deterministic_algorithms(True)
    if algorithm == "gbdt":
        return train_boosted_trees(context, output, epochs, meta["seed"], callback)
    model = baseline_network(algorithm, meta, context)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    labels = torch.as_tensor(context["labels"], dtype=torch.long)
    train = np.flatnonzero(context["splits"] == "train")
    valid = np.flatnonzero(context["splits"] == "val")
    train_snapshot = str(context["snapshots"][train[0]])
    valid_snapshot = str(context["snapshots"][valid[0]])
    best = float("inf")
    selected_epoch = 0
    for epoch in range(1, epochs + 1):
        model.train()
        optimizer.zero_grad()
        logits = model(train_snapshot, train)
        loss = F.cross_entropy(logits, labels[train])
        loss.backward()
        optimizer.step()
        model.eval()
        with torch.inference_mode():
            validation = float(F.cross_entropy(model(valid_snapshot, valid), labels[valid]))
        if not np.isfinite([float(loss.detach()), validation]).all():
            raise ValueError("Non-finite training or validation loss")
        if validation < best:
            best, selected_epoch = validation, epoch
            torch.save(model.state_dict(), output)
        callback({"epoch": epoch, "trainLoss": float(loss.detach()), "validationLoss": validation})
    return selected_epoch
