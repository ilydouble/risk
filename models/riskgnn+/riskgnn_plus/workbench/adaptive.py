"""Missing-aware tabular prediction with a bounded, optional graph correction."""

import torch
from smesd_uncertainty.comrisk_base.utils import hyper_laplacian
from torch import nn

from riskgnn_plus.dst import dempster_shafer_combine_binary
from riskgnn_plus.model import RiskGNNPlus, RiskGNNPlusOutput

ADAPTIVE_ARCHITECTURE = "riskgnn-plus-adaptive-v1"
FUSION_PROFILE = {
    "version": 1,
    "mode": "adaptive",
    "inputDim": 64,
    "outputDim": 32,
    "graphDropout": 0.5,
    "typeDropout": 0.2,
    "featureMissingDropout": 0.1,
    "graphLogitBound": 0.5,
    "nodeAuxWeight": 0.5,
    "learningRate": 0.001,
    "weightDecay": 0.01,
    "inputClip": 10.0,
}


class NormalizedHypergraph(nn.Module):
    def __init__(self, input_dim, output_dim, count):
        super().__init__()
        self.proj = nn.Linear(input_dim, output_dim, bias=False)
        self.alpha = nn.Parameter(torch.zeros(count, 1))

    def forward(self, features, hypers):
        z = self.proj(features)
        result, total = torch.zeros_like(z), z.new_zeros((len(z), 1))
        for i, (node, group, count) in enumerate(hypers):
            if not count:
                continue
            if self.training and torch.rand(()) < FUSION_PROFILE["typeDropout"]:
                continue
            present = torch.bincount(node, minlength=len(z)).gt(0).to(z.dtype)[:, None]
            weight = torch.sigmoid(self.alpha[i])
            result = result + weight * hyper_laplacian(z, node, group, count)
            total = total + weight * present
        # Normalize across the types actually available to each observation.
        return result / total.clamp_min(1e-6)


class AdaptivePlus(RiskGNNPlus):
    def __init__(self, *, meta, **kwargs):
        super().__init__(**kwargs)
        self.hypergnn = NormalizedHypergraph(
            self.input_dim, self.output_dim, len(meta["hyperedgeTypes"])
        )
        self.node_norm = nn.LayerNorm(self.output_dim)
        self.graph_norm = nn.LayerNorm(self.output_dim)
        self.graph_correction = nn.Linear(self.output_dim, 2)
        self.graph_gate = nn.Sequential(
            nn.Linear(2 * self.output_dim + 4, 16), nn.SiLU(), nn.Linear(16, 1)
        )
        nn.init.constant_(self.graph_gate[-1].bias, -2.0)
        names, pre = meta["features"], meta["preprocessing"]
        pairs = [
            (names.index(n[:-8]), i)
            for i, n in enumerate(names)
            if n.endswith("_missing") and n[:-8] in names
        ]
        self.value_columns = [a for a, _ in pairs]
        self.mask_columns = [b for _, b in pairs]
        # These are immutable preprocessing inputs, not learned or graph-size-dependent state.
        self.mask_mean = torch.tensor([pre["mean"][i] for i in self.mask_columns])
        self.mask_scale = torch.tensor([pre["scale"][i] for i in self.mask_columns])
        self.missing_flags = (1 - self.mask_mean) / self.mask_scale
        self.fill_values = torch.tensor(
            [(pre["fillValues"][i] - pre["mean"][i]) / pre["scale"][i] for i in self.value_columns]
        )

    def forward(self, risk_data, company_attr, hete_graph, hyp_graph, idx, community_prior=None):
        attributes = torch.as_tensor(company_attr, dtype=torch.float32).clone()
        if self.mask_columns:
            missing = (attributes[:, self.mask_columns] * self.mask_scale + self.mask_mean) > 0.5
            if self.training:
                missing = missing | (
                    torch.rand(missing.shape) < FUSION_PROFILE["featureMissingDropout"]
                )
            values = attributes[:, self.value_columns]
            attributes[:, self.value_columns] = torch.where(missing, self.fill_values, values)
            attributes[:, self.mask_columns] = torch.where(
                missing, self.missing_flags, attributes[:, self.mask_columns]
            )
            financial_coverage = 1 - missing.float().mean(dim=1)
        else:
            financial_coverage = torch.ones(len(attributes))
        attributes = attributes.clamp(-FUSION_PROFILE["inputClip"], FUSION_PROFILE["inputClip"])
        degree = torch.zeros(self.company_num)
        active_types = torch.zeros_like(degree)
        if self.use_hypergraph:
            for node, _, _ in hyp_graph:
                counts = torch.bincount(node, minlength=self.company_num).float()
                degree += counts
                active_types += counts.gt(0)
        if self.use_edgegraph and len(hete_graph[0]):
            edges = torch.as_tensor(hete_graph[0], dtype=torch.long)
            touched = edges.flatten()
            touched = touched[touched < self.company_num]
            counts = torch.bincount(touched, minlength=self.company_num).float()
            degree += counts
            active_types += counts.gt(0)
        support = degree.gt(0).float()
        self.quality = torch.stack(
            (
                financial_coverage,
                support,
                active_types / max(1, len(hyp_graph) + 1),
                torch.log1p(degree).clamp_max(5) / 5,
            ),
            dim=1,
        )[idx]
        self.graph_available = support[idx, None]
        return super().forward(risk_data, attributes, hete_graph, hyp_graph, idx, community_prior)

    def extract_node_representation(self, risk_data, company_attr, idx, community_prior=None):
        # Random entity identity vectors cannot generalize to held-out companies.
        original = self.company_emb
        self.company_emb = torch.zeros_like(original)
        try:
            return super().extract_node_representation(
                risk_data, company_attr, idx, community_prior
            )
        finally:
            self.company_emb = original

    def classify(self, node_latent, graph_latent):
        node = self.node_norm(node_latent)
        graph = self.graph_norm(graph_latent)
        gate = torch.sigmoid(self.graph_gate(torch.cat((node, graph, self.quality), dim=1)))
        gate = gate * self.graph_available
        if self.training:
            gate = gate * (torch.rand_like(gate) >= FUSION_PROFILE["graphDropout"])
        self.last_graph_weight = gate
        node_logits = self.primary_classifier(node)
        correction = FUSION_PROFILE["graphLogitBound"] * torch.tanh(self.graph_correction(graph))
        primary_logits = node_logits + gate * correction
        node_evidence = self.node_evidence_head(node)
        graph_evidence = gate * self.graph_evidence_head(graph)
        dst = dempster_shafer_combine_binary(node_evidence, graph_evidence)
        return RiskGNNPlusOutput(
            probabilities=primary_logits.softmax(dim=-1),
            fused_probabilities=dst.fused_state.probabilities,
            fused_alpha=dst.fused_state.alpha,
            fused_uncertainty=dst.fused_state.uncertainty,
            conflict=dst.conflict,
            node_alpha=dst.node_state.alpha,
            node_uncertainty=dst.node_state.uncertainty,
            node_probabilities=dst.node_state.probabilities,
            graph_alpha=dst.graph_state.alpha,
            graph_uncertainty=dst.graph_state.uncertainty,
            graph_probabilities=dst.graph_state.probabilities,
            primary_logits=primary_logits,
            node_embedding=node,
            graph_embedding=graph,
        )
