"""Dempster-Shafer Theory (DST) and Subjective Logic utilities for RiskGNN+.

Implements belief assignment, cross-branch orthogonal combination (Dempster's Rule),
conflict quantification, and reconstruction of fused Dirichlet distribution parameters.
"""

from __future__ import annotations

from typing import NamedTuple

import torch
import torch.nn.functional as F


class EvidenceState(NamedTuple):
    """Container for evidential parameters of a single branch or fused outcome."""

    evidence: torch.Tensor       # [B, K], non-negative evidence e_k >= 0
    alpha: torch.Tensor          # [B, K], Dirichlet parameters alpha_k = e_k + 1
    strength: torch.Tensor       # [B, 1], Dirichlet Dirichlet strength S = sum(alpha_k)
    belief_mass: torch.Tensor    # [B, K], belief mass m_k = e_k / S
    uncertainty: torch.Tensor    # [B], epistemic uncertainty u = K / S
    probabilities: torch.Tensor  # [B, K], expected class probabilities p_k = alpha_k / S


class DSTFusionOutput(NamedTuple):
    """Full bundle returned after Dempster-Shafer fusion."""

    node_state: EvidenceState
    graph_state: EvidenceState
    fused_state: EvidenceState
    conflict: torch.Tensor       # [B], degree of inter-branch conflict C in [0, 1)


def compute_evidence_state(
    evidence: torch.Tensor,
    num_classes: int = 2,
    eps: float = 1e-7,
) -> EvidenceState:
    """Convert raw non-negative evidence vectors into a Subjective Logic EvidenceState.

    Args:
        evidence: Tensor of shape [B, K], non-negative evidence.
        num_classes: Number of categorical classes K (default 2 for default prediction).
        eps: Small epsilon for numerical stability.

    Returns:
        EvidenceState with alpha, S, belief masses m, uncertainty u, and probabilities.
    """
    evidence = F.relu(evidence)
    alpha = evidence + 1.0
    strength = torch.sum(alpha, dim=-1, keepdim=True).clamp_min(eps)
    belief_mass = evidence / strength
    uncertainty = (float(num_classes) / strength.squeeze(-1)).clamp(0.0, 1.0)
    probabilities = alpha / strength
    return EvidenceState(
        evidence=evidence,
        alpha=alpha,
        strength=strength,
        belief_mass=belief_mass,
        uncertainty=uncertainty,
        probabilities=probabilities,
    )


def dempster_shafer_combine_binary(
    node_evidence: torch.Tensor,
    graph_evidence: torch.Tensor,
    eps: float = 1e-7,
) -> DSTFusionOutput:
    """Fuse binary evidence from the Node and Graph branches using Dempster's rule.

    For K = 2:
        m_k = (m1_k * m2_k + m1_k * u2 + m2_k * u1) / (1 - C)
        u   = (u1 * u2) / (1 - C)
        C   = m1_0 * m2_1 + m1_1 * m2_0

    Key Mathematical Invariants:
        1. sum_k m_k + u == 1.0 identically.
        2. When Graph is completely uninformative (u2 -> 1, m2 -> 0),
           fused state automatically degenerates to the Node state (m -> m1, u -> u1).
        3. When Node and Graph make high-confidence opposing predictions,
           conflict C -> 1 triggers a high-conflict contagion warning.

    Args:
        node_evidence: [B, 2] non-negative evidence from Node/Tabular branch.
        graph_evidence: [B, 2] non-negative evidence from Graph/Topology branch.
        eps: Epsilon to prevent division by zero when conflict approaches 1.

    Returns:
        DSTFusionOutput with node_state, graph_state, fused_state, and conflict.
    """
    node_state = compute_evidence_state(node_evidence, num_classes=2, eps=eps)
    graph_state = compute_evidence_state(graph_evidence, num_classes=2, eps=eps)

    m_n = node_state.belief_mass        # [B, 2]
    u_n = node_state.uncertainty        # [B]
    m_g = graph_state.belief_mass       # [B, 2]
    u_g = graph_state.uncertainty       # [B]

    # Conflict degree C = m_node[0] * m_graph[1] + m_node[1] * m_graph[0]
    conflict = m_n[:, 0] * m_g[:, 1] + m_n[:, 1] * m_g[:, 0]  # [B]
    one_minus_c = (1.0 - conflict).clamp_min(eps).unsqueeze(-1)  # [B, 1]

    # Fused belief mass for class k:
    # numerator_k = m_n[:, k] * m_g[:, k] + m_n[:, k] * u_g + m_g[:, k] * u_n
    u_g_exp = u_g.unsqueeze(-1)  # [B, 1]
    u_n_exp = u_n.unsqueeze(-1)  # [B, 1]
    fused_mass_num = m_n * m_g + m_n * u_g_exp + m_g * u_n_exp  # [B, 2]
    fused_mass = (fused_mass_num / one_minus_c).clamp(min=0.0, max=1.0)

    # Fused uncertainty:
    fused_u_num = u_n * u_g  # [B]
    fused_u = (fused_u_num / one_minus_c.squeeze(-1)).clamp(min=0.0, max=1.0)

    # Reconstruct fused Dirichlet parameters:
    # S_tilde = K / u_fused
    # e_tilde_k = m_k * S_tilde = 2.0 * m_k / u_fused
    # alpha_tilde_k = e_tilde_k + 1
    safe_u = fused_u.clamp_min(eps).unsqueeze(-1)  # [B, 1]
    fused_evidence = (2.0 * fused_mass / safe_u).clamp_min(0.0)
    fused_alpha = fused_evidence + 1.0
    fused_strength = torch.sum(fused_alpha, dim=-1, keepdim=True).clamp_min(eps)
    fused_prob = fused_alpha / fused_strength

    fused_state = EvidenceState(
        evidence=fused_evidence,
        alpha=fused_alpha,
        strength=fused_strength,
        belief_mass=fused_mass,
        uncertainty=fused_u,
        probabilities=fused_prob,
    )

    return DSTFusionOutput(
        node_state=node_state,
        graph_state=graph_state,
        fused_state=fused_state,
        conflict=conflict,
    )
