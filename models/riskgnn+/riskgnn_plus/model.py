"""RiskGNN+ Architecture: Dual-Branch Evidence Learning with DST Fusion.

Combines the Node/Tabular representation branch and the Heterogeneous Graph
propagation branch through Dempster-Shafer orthogonal combination, eliminating
the need for error-prone scalar edge confidence inputs.
"""

from __future__ import annotations

from typing import NamedTuple

import torch
import torch.nn as nn
import torch.nn.functional as F

from smesd_uncertainty.comrisk_base.gnn import (
    HeteGNN,
    HyperGNN,
    HyperGNNVectorized,
    RiskInfo,
)
from .dst import DSTFusionOutput, dempster_shafer_combine_binary


class RiskGNNPlusOutput(NamedTuple):
    """Rich output object produced by RiskGNNPlus."""

    probabilities: torch.Tensor       # [B, 2] primary calibrated prediction probabilities
    fused_probabilities: torch.Tensor # [B, 2] DST fused prediction probabilities
    fused_alpha: torch.Tensor         # [B, 2] fused Dirichlet parameters
    fused_uncertainty: torch.Tensor   # [B] fused epistemic uncertainty in [0, 1]
    conflict: torch.Tensor            # [B] inter-branch conflict degree C in [0, 1)

    node_alpha: torch.Tensor          # [B, 2] Node branch Dirichlet parameters
    node_uncertainty: torch.Tensor    # [B] Node branch uncertainty
    node_probabilities: torch.Tensor  # [B, 2] Node branch probabilities

    graph_alpha: torch.Tensor         # [B, 2] Graph branch Dirichlet parameters
    graph_uncertainty: torch.Tensor   # [B] Graph branch uncertainty
    graph_probabilities: torch.Tensor # [B, 2] Graph branch probabilities

    primary_logits: torch.Tensor      # [B, 2] discriminative backbone logits (0.83+ capacity)
    node_embedding: torch.Tensor      # [B, D] internal node representation
    graph_embedding: torch.Tensor     # [B, D] internal graph representation


class EvidentialClassifier(nn.Module):
    """Calibrated Evidential Projection Layer mapping GNN representations to Dirichlet evidence."""

    def __init__(self, in_features: int, num_classes: int = 2) -> None:
        super().__init__()
        self.linear = nn.Linear(in_features, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        logits = self.linear(x)
        # exp activation maps logits to evidence in [0, inf)
        return torch.exp(torch.clamp(logits, -10.0, 10.0))


class RiskGNNPlus(nn.Module):
    """RiskGNN+ with Node/Graph Evidence Dual-Branch and DST Fusion.

    Architecture highlights:
    1. Node Branch (Internal fundamental health):
       Combines enterprise base attributes, financial metrics, and court/risk event records.
       Outputs node evidence e_node, Dirichlet alpha_node, and node uncertainty u_node.
    2. Graph Branch (Exogenous network contagion):
       Propagates relational risk across heterogeneous edges (shareholding, director, legal).
       Outputs graph evidence e_graph, Dirichlet alpha_graph, and graph uncertainty u_graph.
    3. DST Fusion:
       Synthesizes node and graph beliefs using Dempster's rule.
       When the graph is uninformative or an isolated node, u_graph -> 1, and the model
       smoothly and analytically degenerates to the Node branch without performance loss.
       When Node and Graph contradict each other, conflict C -> 1 flags high contagion friction.
    """

    def __init__(
        self,
        input_dim: int,
        output_dim: int,
        company_num: int,
        person_num: int,
        rel_num: int,
        cause_type_num: int,
        device: torch.device,
        com_initial_emb: object,
        person_initial_emb: object,
        court_type_num: int = 4,
        category_num: int = 4,
        time_label_num: int = 5,
        dropout: float = 0.2,
        use_hypergraph: bool = True,
        use_edgegraph: bool = True,
        n_company_attr_dims: int = 3,
        hyper_impl: str = "scipy",
        hete_scalar_weights: object = None,
        use_community_prior: bool = True,
        evidence_hidden_dim: int = 32,
    ) -> None:
        super().__init__()
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.company_num = company_num
        self.person_num = person_num
        self.rel_num = rel_num
        self.device = device
        self.use_hypergraph = use_hypergraph
        self.use_edgegraph = use_edgegraph
        self.hyper_impl = hyper_impl
        self.use_community_prior = use_community_prior

        # Embeddings & Projections
        self.company_emb = torch.FloatTensor(com_initial_emb).to(device)
        self.person_emb = torch.FloatTensor(person_initial_emb).to(device)
        self.company_proj = nn.Linear(32, input_dim, bias=False)
        self.person_proj = nn.Linear(32, input_dim, bias=False)

        # Risk information & priors
        self.riskinfo = RiskInfo(
            input_dim,
            company_num,
            cause_type_num,
            court_type_num,
            category_num,
            time_label_num=time_label_num,
            device=device,
        )
        prior_dims = 1 if use_community_prior else 0
        self.risk_proj = nn.Linear(
            input_dim + n_company_attr_dims + 20 + prior_dims,
            input_dim,
            bias=False,
        )

        # Hypergraph module
        if hyper_impl == "vectorized":
            self.hypergnn = HyperGNNVectorized(input_dim, output_dim, num_layer=1)
        else:
            self.hypergnn = HyperGNN(input_dim, output_dim, num_layer=1)

        # Heterogeneous GNN 5-layer propagation stack
        self.hetegnn = nn.ModuleList()
        for i in range(5):
            in_d = input_dim if i == 0 else output_dim
            self.hetegnn.append(
                HeteGNN(in_d, output_dim, rel_num, use_scalar_weights=hete_scalar_weights)
            )

        self.info_proj = nn.Linear(output_dim, output_dim, bias=False)
        self.final_proj = nn.Sequential(
            nn.Linear(input_dim, output_dim, bias=False),
            nn.ReLU(),
            nn.Linear(output_dim, output_dim, bias=False),
        )
        self.alpha = nn.Parameter(torch.ones(1, device=device))

        # Primary discriminative classifier (preserving RiskGNN 0.82+ capacity)
        self.primary_classifier = nn.Linear(output_dim, 2)

        # --- Dual-Branch Evidence Heads (DST Uncertainty & Triage) ---
        self.node_evidence_head = EvidentialClassifier(
            in_features=output_dim, num_classes=2
        )
        self.graph_evidence_head = EvidentialClassifier(
            in_features=output_dim, num_classes=2
        )

    def extract_node_representation(
        self,
        risk_data: object,
        company_attr: object,
        idx: object,
        community_prior: object = None,
    ) -> torch.Tensor:
        """Extract purely node-level (tabular + events + priors) representation."""
        company_emb = self.company_proj(self.company_emb)
        company_basic_info = torch.zeros(
            (self.company_num, len(company_attr[0])), device=self.device
        )
        company_attr_t = torch.as_tensor(company_attr, dtype=torch.float32, device=self.device)
        if company_attr_t.shape[0] == len(idx):
            company_basic_info[idx] = company_attr_t
        elif company_attr_t.shape[0] == self.company_num:
            company_basic_info[idx] = company_attr_t[idx]
        else:
            raise ValueError(f"company_attr length {company_attr_t.shape[0]} matches neither idx ({len(idx)}) nor company_num ({self.company_num})")

        if self.use_community_prior:
            community_feat = torch.zeros((self.company_num, 1), device=self.device)
            if community_prior is not None:
                community_feat[idx] = torch.Tensor(community_prior).to(self.device)
            company_basic_info = torch.cat((company_basic_info, community_feat), dim=1)

        company_emb = torch.cat((company_emb, company_basic_info), dim=1)
        if risk_data:
            # Only run through riskinfo if non-empty events exist
            has_events = any(len(risk_data.get(i, [])) > 0 for i in risk_data)
            if has_events:
                risk_info = self.riskinfo(risk_data)
            else:
                risk_info = torch.zeros((self.company_num, 20), device=self.device)
        else:
            risk_info = torch.zeros((self.company_num, 20), device=self.device)
        company_emb_info = self.risk_proj(torch.cat((company_emb, risk_info), dim=1))
        return company_emb_info

    def forward(
        self,
        risk_data: object,
        company_attr: object,
        hete_graph: object,
        hyp_graph: object,
        idx: object,
        community_prior: object = None,
    ) -> RiskGNNPlusOutput:
        """Full forward pass: Node extraction, Graph propagation, and DST fusion."""
        # 1. Node representation
        company_emb_info = self.extract_node_representation(
            risk_data, company_attr, idx, community_prior
        )
        node_latent = self.final_proj(company_emb_info[idx])

        # 2. Graph propagation
        person_emb = self.person_proj(self.person_emb)
        if self.use_hypergraph:
            company_emb_hyper = self.hypergnn(company_emb_info, hyp_graph)
        else:
            company_emb_hyper = torch.zeros(
                (self.company_num, self.output_dim), device=self.device
            )

        if self.use_edgegraph:
            if len(hete_graph) == 4:
                edge_index, edge_type, edge_weight, edge_confidence = hete_graph
            else:
                edge_index, edge_type, edge_weight = hete_graph
                edge_confidence = None

            company_emb_hete = company_emb_info
            for i in range(5):
                company_emb_hete, person_emb = self.hetegnn[i](
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
            company_emb_hete = torch.zeros(
                (self.company_num, self.output_dim), device=self.device
            )

        graph_aggregated = self.info_proj(company_emb_hyper + company_emb_hete)
        # Graph latent uses F.gelu as in standard RiskGNN
        graph_latent = F.gelu(graph_aggregated[idx])

        # 3. Dual-Branch Evidence Generation
        e_node = self.node_evidence_head(node_latent)
        e_graph = self.graph_evidence_head(graph_latent)

        # 4. Dempster-Shafer Orthogonal Fusion
        dst_out: DSTFusionOutput = dempster_shafer_combine_binary(e_node, e_graph)

        # 5. Primary Discriminative Stream (RiskGNN Backbone fusion)
        alpha = torch.sigmoid(self.alpha)
        backbone_emb = alpha * graph_latent + (1.0 - alpha) * node_latent
        primary_logits = self.primary_classifier(backbone_emb)
        primary_probs = F.softmax(primary_logits, dim=-1)

        return RiskGNNPlusOutput(
            probabilities=primary_probs,
            fused_probabilities=dst_out.fused_state.probabilities,
            fused_alpha=dst_out.fused_state.alpha,
            fused_uncertainty=dst_out.fused_state.uncertainty,
            conflict=dst_out.conflict,
            node_alpha=dst_out.node_state.alpha,
            node_uncertainty=dst_out.node_state.uncertainty,
            node_probabilities=dst_out.node_state.probabilities,
            graph_alpha=dst_out.graph_state.alpha,
            graph_uncertainty=dst_out.graph_state.uncertainty,
            graph_probabilities=dst_out.graph_state.probabilities,
            primary_logits=primary_logits,
            node_embedding=node_latent,
            graph_embedding=graph_latent,
        )

    def forward_batch(
        self,
        company_attr_all: object,
        edge_index_local: torch.Tensor,
        edge_type_local: torch.Tensor,
        edge_weight_local: torch.Tensor,
        n_id: torch.Tensor,
        batch_size: int,
        community_prior_all: object = None,
    ) -> RiskGNNPlusOutput:
        """Mini-batch forward pass for scalable subgraphs via NeighborLoader."""
        n = len(n_id)
        n_id_np = n_id.detach().cpu().numpy()
        company_emb = self.company_proj(self.company_emb[n_id])
        person_emb = self.person_proj(self.person_emb)
        attr = torch.as_tensor(
            company_attr_all[n_id_np], dtype=torch.float32, device=self.device
        )
        company_basic_info = attr

        if self.use_community_prior:
            if community_prior_all is not None:
                prior = torch.as_tensor(
                    community_prior_all[n_id_np], dtype=torch.float32, device=self.device
                ).reshape(-1, 1)
            else:
                prior = torch.zeros((n, 1), device=self.device)
            company_basic_info = torch.cat((company_basic_info, prior), dim=1)

        company_emb = torch.cat((company_emb, company_basic_info), dim=1)
        risk_info = torch.zeros((n, 20), device=self.device)
        company_emb_info = self.risk_proj(torch.cat((company_emb, risk_info), dim=1))

        # Node branch features for target batch
        node_latent = self.final_proj(company_emb_info[:batch_size])

        # Graph propagation over sampled local neighborhood
        if edge_index_local.shape[0] > 0:
            company_emb_hete = company_emb_info
            for i in range(5):
                company_emb_hete, person_emb = self.hetegnn[i](
                    company_emb_hete,
                    person_emb,
                    edge_index_local,
                    edge_type_local,
                    edge_weight_local,
                    n,
                    0,
                    None,
                )
        else:
            company_emb_hete = torch.zeros((n, self.output_dim), device=self.device)

        graph_latent = self.info_proj(company_emb_hete[:batch_size])

        # Evidence generation
        e_node = self.node_evidence_head(node_latent)
        e_graph = self.graph_evidence_head(graph_latent)

        # DST Fusion
        dst_out = dempster_shafer_combine_binary(e_node, e_graph)

        # Primary Backbone Stream
        alpha = torch.sigmoid(self.alpha)
        backbone_emb = alpha * graph_latent + (1.0 - alpha) * node_latent
        primary_logits = self.primary_classifier(backbone_emb)
        primary_probs = F.softmax(primary_logits, dim=-1)

        return RiskGNNPlusOutput(
            probabilities=primary_probs,
            fused_probabilities=dst_out.fused_state.probabilities,
            fused_alpha=dst_out.fused_state.alpha,
            fused_uncertainty=dst_out.fused_state.uncertainty,
            conflict=dst_out.conflict,
            node_alpha=dst_out.node_state.alpha,
            node_uncertainty=dst_out.node_state.uncertainty,
            node_probabilities=dst_out.node_state.probabilities,
            graph_alpha=dst_out.graph_state.alpha,
            graph_uncertainty=dst_out.graph_state.uncertainty,
            graph_probabilities=dst_out.graph_state.probabilities,
            primary_logits=primary_logits,
            node_embedding=node_latent,
            graph_embedding=graph_latent,
        )
