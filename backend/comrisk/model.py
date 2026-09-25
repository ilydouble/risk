"""Independent ComRisk-inspired implementation using native PyTorch scatter ops."""
from __future__ import annotations

import math
import torch
from torch import nn
from torch.nn import functional as F


def segment_softmax(logits, target, n):
    maxima = logits.new_full((n,), -torch.inf)
    maxima.scatter_reduce_(0, target, logits, reduce="amax", include_self=True)
    exp = (logits - maxima[target]).exp()
    denom = logits.new_zeros(n).index_add(0, target, exp)
    return exp / denom[target].clamp_min(1e-12)


class EventEncoder(nn.Module):
    def __init__(self, hidden):
        super().__init__()
        self.cause = nn.Embedding(11, 12)
        self.court = nn.Embedding(4, 4)
        self.result = nn.Embedding(4, 4)
        self.proj = nn.Linear(20, hidden, bias=False)

    def forward(self, events, n):
        result = self.proj.weight.new_zeros((n, self.proj.out_features))
        if not len(events):
            return result
        emb = torch.cat([self.cause(events[:, 1].long()), self.court(events[:, 2].long()),
                         self.result(events[:, 3].long())], dim=-1)
        age = events[:, 4]
        decay = 1 / (1 + torch.where(age <= 24, 0.01, 0.1) * age)
        return result.index_add(0, events[:, 0].long(), self.proj(emb) * decay[:, None])


class RelationLayer(nn.Module):
    def __init__(self, hidden, relations, dropout):
        super().__init__()
        self.values = nn.ModuleList([nn.Linear(hidden, hidden, bias=False) for _ in range(relations)])
        self.attention = nn.ModuleList([nn.Linear(2 * hidden, 1, bias=False) for _ in range(relations)])
        self.keys = nn.ModuleList([nn.Linear(hidden, hidden, bias=False) for _ in range(relations)])
        self.query = nn.Linear(hidden, hidden, bias=False)
        self.priors = nn.Parameter(torch.ones(relations))
        self.neighbor_gate = nn.Linear(2 * hidden, hidden)
        self.norm = nn.LayerNorm(hidden)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x, relations):
        n, d = x.shape
        outputs, scores, available = [], [], []
        q = self.query(x)
        for i, (source, target, weight) in enumerate(relations):
            msg = x.new_zeros((n, d))
            mask = torch.zeros(n, dtype=torch.bool, device=x.device)
            if len(source):
                # Explicit positive edge weight prior instead of guessing edge semantics by sum.
                logits = F.leaky_relu(self.attention[i](torch.cat([x[target], x[source]], -1)).squeeze(-1), 0.2)
                alpha = segment_softmax(logits + weight.log(), target, n)
                msg = msg.index_add(0, target, self.values[i](x[source]) * alpha[:, None])
                mask[target] = True
            outputs.append(msg)
            scores.append((q * self.keys[i](msg)).sum(-1) * self.priors[i] / math.sqrt(d))
            available.append(mask)
        mask = torch.stack(available, dim=1)
        scores = torch.stack(scores, dim=1).masked_fill(~mask, -1e9)
        alpha = scores.softmax(1) * mask
        aggregate = (torch.stack(outputs, dim=1) * alpha[:, :, None]).sum(1)
        gate = self.neighbor_gate(torch.cat([x, aggregate], dim=-1)).sigmoid()
        return self.norm(x + gate * self.dropout(F.gelu(aggregate)))


def hyper_laplacian(x, node, group, count):
    """(I - Dv^-1/2 H De^-1 H^T Dv^-1/2) X, O(incidences * hidden)."""
    if count == 0:
        return torch.zeros_like(x)
    degree = torch.bincount(node, minlength=len(x)).to(x.dtype)
    inv = degree.clamp_min(1).rsqrt()
    edge_degree = torch.bincount(group, minlength=count).to(x.dtype).clamp_min(1)
    summed = x.new_zeros((count, x.shape[1])).index_add(0, group, x[node] * inv[node, None])
    propagated = torch.zeros_like(x).index_add(0, node, (summed / edge_degree[:, None])[group]) * inv[:, None]
    # Isolated nodes have no group risk; do not fabricate it as an identity term.
    return (x - propagated) * (degree > 0)[:, None]


class ComRisk(nn.Module):
    def __init__(self, feature_dim, relation_count, hyperedge_count, hidden=32, layers=2, dropout=0.15, use_prior=True):
        super().__init__()
        self.feature = nn.Linear(feature_dim * 2, hidden)
        self.node_type = nn.Embedding(2, hidden)
        self.events = EventEncoder(hidden)
        self.layers = nn.ModuleList([RelationLayer(hidden, relation_count, dropout) for _ in range(layers)])
        self.hyper_proj = nn.Linear(hidden, hidden, bias=False)
        self.hyper_weight = nn.Parameter(torch.zeros(hyperedge_count))
        self.self_proj = nn.Sequential(nn.Linear(hidden, hidden), nn.GELU())
        self.graph_proj = nn.Linear(hidden, hidden)
        self.gate = nn.Parameter(torch.tensor(0.0))
        self.use_prior = use_prior
        self.classifier = nn.Linear(hidden + int(use_prior), 1)
        self.dropout = nn.Dropout(dropout)

    def encode(self, graph, mode="full"):
        if mode not in {"full", "no_graph", "no_hyper", "self_only"}:
            raise ValueError("unknown ablation")
        own = F.gelu(self.feature(graph["x"]) + self.node_type(graph["kinds"]) +
                     self.events(graph["events"], len(graph["x"])))
        intra = self.self_proj(own)
        relational = torch.zeros_like(own)
        if mode not in {"no_graph", "self_only"}:
            relational = own
            for layer in self.layers:
                relational = layer(relational, graph["relations"])
        hyper = torch.zeros_like(own)
        if mode not in {"no_hyper", "self_only"}:
            z = self.hyper_proj(own)
            for i, (node, group, count) in enumerate(graph["incidence"]):
                hyper = hyper + self.hyper_weight[i].sigmoid() * hyper_laplacian(z, node, group, count)
        contagion = F.gelu(self.graph_proj(relational + hyper))
        fused = intra if mode == "self_only" else (1 - self.gate.sigmoid()) * intra + self.gate.sigmoid() * contagion
        return fused

    def forward(self, graph, mode="full"):
        fused = self.dropout(self.encode(graph, mode))
        if self.use_prior:
            fused = torch.cat([fused, graph["prior"]], dim=-1)
        return self.classifier(fused).squeeze(-1)
