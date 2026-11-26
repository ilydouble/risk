"""RiskGNN++: topology-aware evidence calibration on heterogeneous risk graphs.

RiskGNN+ already fuses an intrinsic (node) and an extrinsic (graph) Dirichlet with
Dempster's rule.  This module keeps that backbone but replaces the two-source fusion
with three coupled fixes derived from the contagion analysis:

``A. Relation-decomposed opinions``
    The graph branch is split into one evidence opinion per relation type, so the
    conflicts that a single collapsed head would average away stay observable.

``B. Topology-aware discounting``
    Each relation opinion is discounted by ``(1 - K) ** gamma`` (local
    assortativity: a relation that contradicts the firm's intrinsic belief is a
    candidate contagion carrier, not a vote) and by ``(1 + d) ** -eta`` (degree
    regularisation: hubs do not get to buy certainty by stacking neighbours).

``C. Degree-regularised Dirichlet likelihood``
    The training-time evidence budget is scaled by ``1 / (1 + lambda_d * d / dbar)``
    so high-degree nodes cannot collapse their epistemic uncertainty to zero.

The discriminative primary classifier is untouched, so the contribution is a
calibration/uncertainty one rather than a new accuracy head.
"""

from __future__ import annotations

from typing import NamedTuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from riskgnn_plus.dst import compute_evidence_state
from riskgnn_plus.model import RiskGNNPlus

from .fusion import (
    Opinion,
    multi_source_combine,
    opinion_from_evidence,
    opinion_to_alpha,
)
from .person_attributes import PersonAttributeMeanEncoder


class RiskGNNPlusPlusOutput(NamedTuple):
    """Output of RiskGNN++ (superset of the RiskGNN+ output used by the harnesses)."""

    probabilities: torch.Tensor
    fused_probabilities: torch.Tensor
    fused_alpha: torch.Tensor
    fused_uncertainty: torch.Tensor
    conflict: torch.Tensor

    node_alpha: torch.Tensor
    node_uncertainty: torch.Tensor
    node_probabilities: torch.Tensor

    graph_alpha: torch.Tensor
    graph_uncertainty: torch.Tensor
    graph_probabilities: torch.Tensor

    primary_logits: torch.Tensor
    node_embedding: torch.Tensor
    graph_embedding: torch.Tensor

    fused_alpha_regularized: torch.Tensor  # degree-scaled evidence budget
    fused_alpha_raw: torch.Tensor  # unregularised multi-source DS result
    contagion_conflict: torch.Tensor  # node vs neighbourhood disagreement
    mutual_conflict: torch.Tensor  # neighbour vs neighbour disagreement
    degree: torch.Tensor  # total in-degree of the batch nodes


class RiskGNNPlusPlus(RiskGNNPlus):
    """RiskGNN+ with relation-wise opinions and topology-aware evidence calibration."""

    def __init__(
        self,
        *args: object,
        conflict_exponent: float = 1.0,
        degree_exponent: float = 0.25,
        degree_likelihood_lambda: float = 0.5,
        use_topology_discount: bool = True,
        use_degree_likelihood: bool = True,
        person_attribute_dims: int = 0,
        person_attribute_branch: str = "graph",
        **kwargs: object,
    ) -> None:
        super().__init__(*args, **kwargs)
        if conflict_exponent < 0 or degree_exponent < 0 or degree_likelihood_lambda < 0:
            raise ValueError("RiskGNN++ exponents and lambda must be non-negative")

        self.conflict_exponent = float(conflict_exponent)
        self.degree_exponent = float(degree_exponent)
        self.degree_likelihood_lambda = float(degree_likelihood_lambda)
        self.use_topology_discount = bool(use_topology_discount)
        self.use_degree_likelihood = bool(use_degree_likelihood)

        # One evidential head per relation type.  Sharing output_dim but not weights
        # keeps each relation's opinion identifiable, which is the whole point of A.
        self.relation_evidence_heads = nn.ModuleList(
            [nn.Linear(self.output_dim, 2) for _ in range(self.rel_num)]
        )
        if person_attribute_dims < 0:
            raise ValueError("person_attribute_dims must be non-negative")
        # Disabled by default so old configurations retain their parameters and RNG order.
        self.person_attribute_encoder = (
            PersonAttributeMeanEncoder(person_attribute_dims, self.output_dim)
            if person_attribute_dims
            else None
        )
        self.set_person_attribute_branch(person_attribute_branch)

    def set_person_attribute_branch(self, branch: str) -> None:
        if branch not in ("graph", "node", "both"):
            raise ValueError("person_attribute_branch must be graph, node or both")
        if branch in ("node", "both") and self.person_attribute_encoder is None:
            raise ValueError("Node person context requires a person attribute encoder")
        first = self.final_proj[0]
        width = self.input_dim + (self.output_dim if branch in ("node", "both") else 0)
        if first.in_features != width:
            # Preserve shared initialization and RNG; new person columns start at zero.
            with torch.random.fork_rng(devices=[]):
                replacement = nn.Linear(width, self.output_dim, bias=False)
            replacement = replacement.to(device=first.weight.device, dtype=first.weight.dtype)
            with torch.no_grad():
                replacement.weight.zero_()
                replacement.weight[:, : self.input_dim].copy_(first.weight[:, : self.input_dim])
            self.final_proj[0] = replacement
        self.person_attribute_branch = branch

    def _unpack_graph(self, hete_graph: object) -> tuple[torch.Tensor, torch.Tensor]:
        if len(hete_graph) == 4:
            edge_index, edge_type = hete_graph[0], hete_graph[1]
        else:
            edge_index, edge_type = hete_graph[0], hete_graph[1]
        edge_index = torch.as_tensor(edge_index, dtype=torch.long, device=self.device)
        edge_type = torch.as_tensor(edge_type, dtype=torch.long, device=self.device)
        return edge_index, edge_type

    def _relation_opinions(
        self,
        full_latent: torch.Tensor,
        edge_index: torch.Tensor,
        edge_type: torch.Tensor,
        idx: torch.Tensor,
    ) -> tuple[list[Opinion], torch.Tensor]:
        """Pool each relation's neighbours and turn them into one opinion per relation.

        ``full_latent`` covers companies *and* person nodes in the original
        ``company-first`` index space, because SMEsD relation types 0-5 and 8-9 have
        person endpoints.  Edges whose type is ``>= rel_num`` are ignored, matching
        the base ``HeteGNN`` loop which only ever indexes relations ``0..rel_num-1``.
        """
        source, target = edge_index[:, 0], edge_index[:, 1]
        num_all = full_latent.shape[0]
        considered = edge_type < self.rel_num
        degrees = torch.bincount(target[considered], minlength=num_all).to(full_latent.dtype)

        opinions: list[Opinion] = []
        for relation in range(self.rel_num):
            mask = edge_type == relation
            relation_degree = torch.bincount(target[mask], minlength=num_all).to(full_latent.dtype)
            pooled = torch.zeros_like(full_latent)
            if bool(mask.any()):
                pooled.index_add_(0, target[mask], full_latent[source[mask]])
            # Self is always pooled so isolated nodes still yield a well-defined,
            # fully vacuous-ish opinion instead of a zero-vector artefact.
            pooled = (pooled + full_latent) / (relation_degree + 1.0).unsqueeze(-1)
            evidence = torch.exp(
                torch.clamp(self.relation_evidence_heads[relation](pooled[idx]), -10.0, 10.0)
            )
            opinions.append(opinion_from_evidence(evidence))
        return opinions, degrees

    def _intrinsic_latent(self, company_info, person_context, idx, company_attr):
        node_input = company_info[idx]
        if self.person_attribute_branch in ("node", "both"):
            node_input = torch.cat((node_input, person_context[idx]), dim=-1)
        return self.final_proj(node_input)

    def _primary_logits(self, node_latent, graph_latent):
        alpha = torch.sigmoid(self.alpha)
        return self.primary_classifier(alpha * graph_latent + (1.0 - alpha) * node_latent)

    def forward(
        self,
        risk_data: object,
        company_attr: object,
        hete_graph: object,
        hyp_graph: object,
        idx: object,
        community_prior: object = None,
        *,
        person_attributes: object = None,
        person_company_edges: object = None,
    ) -> RiskGNNPlusPlusOutput:
        idx_tensor = torch.as_tensor(idx, dtype=torch.long, device=self.device)

        # --- identical backbone to RiskGNN+, so any difference is the calibration ---
        company_emb_info = self.extract_node_representation(
            risk_data, company_attr, idx, community_prior
        )
        person_context = None
        if self.person_attribute_encoder is not None:
            person_context = self.person_attribute_encoder(
                person_attributes, person_company_edges, self.company_num
            )
        elif person_attributes is not None or person_company_edges is not None:
            raise ValueError("Model was not configured to consume person attributes")
        node_latent = self._intrinsic_latent(
            company_emb_info, person_context, idx_tensor, company_attr
        )

        person_emb = self.person_proj(self.person_emb)
        if self.use_hypergraph:
            company_emb_hyper = self.hypergnn(company_emb_info, hyp_graph)
        else:
            company_emb_hyper = torch.zeros((self.company_num, self.output_dim), device=self.device)

        edge_index, edge_type = self._unpack_graph(hete_graph)
        if self.use_edgegraph:
            if len(hete_graph) == 4:
                edge_weight, edge_confidence = hete_graph[2], hete_graph[3]
            else:
                edge_weight, edge_confidence = hete_graph[2], None
            company_emb_hete = company_emb_info
            for layer in self.hetegnn:
                company_emb_hete, person_emb = layer(
                    company_emb_hete,
                    person_emb,
                    edge_index,
                    edge_type,
                    edge_weight,
                    self.company_num,
                    self.person_num,
                    edge_confidence,
                )
        else:
            company_emb_hete = torch.zeros((self.company_num, self.output_dim), device=self.device)

        graph_input = company_emb_hyper + company_emb_hete
        if person_context is not None and self.person_attribute_branch in ("graph", "both"):
            graph_input = graph_input + person_context
        graph_aggregated = self.info_proj(graph_input)
        graph_latent_full = F.gelu(graph_aggregated)
        graph_latent = graph_latent_full[idx_tensor]

        primary_logits = self._primary_logits(node_latent, graph_latent)
        primary_probs = F.softmax(primary_logits, dim=-1)

        # --- A. relation-decomposed opinions ---
        e_node = self.node_evidence_head(node_latent)
        e_graph = self.graph_evidence_head(graph_latent)
        node_state = compute_evidence_state(e_node, num_classes=2)
        graph_state = compute_evidence_state(e_graph, num_classes=2)
        node_opinion = Opinion(mass=node_state.belief_mass, uncertainty=node_state.uncertainty)
        full_latent = torch.cat((graph_latent_full, person_emb), dim=0)
        relation_opinions, degrees = self._relation_opinions(
            full_latent, edge_index, edge_type, idx_tensor
        )
        node_degree = degrees[idx_tensor]

        # --- B. topology-aware discounting ---
        discounts: list[torch.Tensor] = []
        for opinion in relation_opinions:
            if self.use_topology_discount:
                # (1 - K) is the non-conflict share between the intrinsic belief and
                # this relation; raising it to the conflict exponent discounts
                # relations that contradict the firm.
                non_conflict = (
                    1.0
                    - (
                        node_opinion.mass[:, 0] * opinion.mass[:, 1]
                        + node_opinion.mass[:, 1] * opinion.mass[:, 0]
                    )
                ).clamp(0.0, 1.0)
                factor = non_conflict.pow(self.conflict_exponent)
                factor = factor * (1.0 + node_degree).pow(-self.degree_exponent)
            else:
                factor = torch.ones_like(node_degree)
            discounts.append(factor)

        fused_opinion, contagion_conflict, mutual_conflict = multi_source_combine(
            node_opinion, relation_opinions, discounts
        )
        fused_alpha = opinion_to_alpha(fused_opinion)

        # --- C. degree-regularised evidence budget for the training likelihood ---
        mean_degree = node_degree.mean().clamp_min(1.0).detach()
        if self.use_degree_likelihood:
            budget = 1.0 / (
                1.0 + self.degree_likelihood_lambda * node_degree.detach() / (mean_degree + 1.0)
            )
        else:
            budget = torch.ones_like(node_degree)
        fused_alpha_regularized = 1.0 + budget.unsqueeze(-1) * (fused_alpha - 1.0)

        fused_strength = fused_alpha_regularized.sum(dim=-1, keepdim=True).clamp_min(1e-7)
        fused_probs = fused_alpha_regularized / fused_strength
        fused_uncertainty = (2.0 / fused_strength.squeeze(-1)).clamp(0.0, 1.0)

        return RiskGNNPlusPlusOutput(
            probabilities=primary_probs,
            fused_probabilities=fused_probs,
            fused_alpha=fused_alpha_regularized,
            fused_uncertainty=fused_uncertainty,
            conflict=0.5 * (contagion_conflict + mutual_conflict),
            node_alpha=node_state.alpha,
            node_uncertainty=node_state.uncertainty,
            node_probabilities=node_state.probabilities,
            graph_alpha=graph_state.alpha,
            graph_uncertainty=graph_state.uncertainty,
            graph_probabilities=graph_state.probabilities,
            primary_logits=primary_logits,
            node_embedding=node_latent,
            graph_embedding=graph_latent,
            fused_alpha_regularized=fused_alpha_regularized,
            fused_alpha_raw=fused_alpha,
            contagion_conflict=contagion_conflict,
            mutual_conflict=mutual_conflict,
            degree=node_degree,
        )
