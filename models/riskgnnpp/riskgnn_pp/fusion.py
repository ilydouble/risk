"""Multi-source subjective-logic fusion for RiskGNN++.

RiskGNN+ fuses exactly two Dirichlet opinions (node vs graph) and therefore can
only ever report one inter-branch conflict.  Contagion, however, is a *multi-source*
phenomenon: a firm can agree with its equity neighbours while disagreeing with its
address cluster, and neither disagreement is visible once the graph branch has been
collapsed into a single evidence head.

This module keeps every source as its own opinion, discounts each source by a
topology-aware reliability factor, and combines them with Dempster's rule while
retaining both the node-vs-neighbourhood conflict (contagion) and the
neighbour-vs-neighbour conflict (relational noise).
"""

from __future__ import annotations

from typing import NamedTuple

import torch

EPS = 1e-7


class Opinion(NamedTuple):
    """Binary subjective-logic opinion.

    ``mass`` holds belief masses ``m_k`` for the two classes and ``uncertainty``
    holds the vacuous mass ``u``; ``sum_k m_k + u == 1`` holds by construction.
    """

    mass: torch.Tensor  # [B, 2]
    uncertainty: torch.Tensor  # [B]


def opinion_from_evidence(evidence: torch.Tensor, num_classes: int = 2) -> Opinion:
    """Map non-negative evidence to a subjective-logic opinion via Dirichlet strength."""
    evidence = torch.relu(evidence)
    alpha = evidence + 1.0
    strength = torch.sum(alpha, dim=-1, keepdim=True).clamp_min(EPS)
    mass = evidence / strength
    uncertainty = (float(num_classes) / strength.squeeze(-1)).clamp(0.0, 1.0)
    return Opinion(mass=mass, uncertainty=uncertainty)


def opinion_to_alpha(opinion: Opinion, num_classes: int = 2) -> torch.Tensor:
    """Reconstruct Dirichlet parameters from an opinion (inverse of the mapping above)."""
    uncertainty = opinion.uncertainty.clamp_min(EPS).unsqueeze(-1)
    evidence = (float(num_classes) * opinion.mass / uncertainty).clamp_min(0.0)
    return evidence + 1.0


def pairwise_conflict(first: Opinion, second: Opinion) -> torch.Tensor:
    """Dempster's degree of conflict ``K`` between two binary opinions in [0, 1]."""
    return first.mass[:, 0] * second.mass[:, 1] + first.mass[:, 1] * second.mass[:, 0]


def discount_opinion(opinion: Opinion, factor: torch.Tensor) -> Opinion:
    """Apply a reliability discount ``a in [0, 1]`` to the belief mass of an opinion.

    Discounting pushes mass from the classes into the vacuous mass, which is how
    subjective logic models an unreliable source; ``a == 1`` is the identity and
    ``a == 0`` makes the source completely vacuous.
    """
    factor = factor.clamp(0.0, 1.0).unsqueeze(-1)
    mass = opinion.mass * factor
    uncertainty = (1.0 - factor.squeeze(-1) * (1.0 - opinion.uncertainty)).clamp(0.0, 1.0)
    return Opinion(mass=mass, uncertainty=uncertainty)


def combine_opinions(first: Opinion, second: Opinion) -> tuple[Opinion, torch.Tensor]:
    """Dempster's orthogonal combination of two binary opinions.

    Returns the fused opinion and the pairwise conflict that was absorbed by the
    normalising constant ``1 - K``.
    """
    conflict = pairwise_conflict(first, second)
    denominator = (1.0 - conflict).clamp_min(EPS).unsqueeze(-1)

    u1 = first.uncertainty.unsqueeze(-1)
    u2 = second.uncertainty.unsqueeze(-1)
    numerator = first.mass * second.mass + first.mass * u2 + second.mass * u1
    mass = (numerator / denominator).clamp(0.0, 1.0)
    uncertainty = (first.uncertainty * second.uncertainty / denominator.squeeze(-1)).clamp(0.0, 1.0)
    return Opinion(mass=mass, uncertainty=uncertainty), conflict


def multi_source_combine(
    node_opinion: Opinion,
    relation_opinions: list[Opinion],
    discounts: list[torch.Tensor],
) -> tuple[Opinion, torch.Tensor, torch.Tensor]:
    """Fuse the node opinion with every discounted relation opinion.

    Args:
        node_opinion: intrinsic (feature-only) opinion, used as the fusion anchor.
        relation_opinions: one opinion per relation type.
        discounts: reliability factor per relation opinion, each shaped ``[B]``.

    Returns:
        ``(fused, contagion_conflict, mutual_conflict)`` where

        * ``contagion_conflict`` is the mean node-vs-neighbour disagreement, i.e. the
          "healthy firm surrounded by a contagion cluster" signal;
        * ``mutual_conflict`` is the mean neighbour-vs-neighbour disagreement, i.e.
          the "relations in the neighbourhood contradict each other" signal.
    """
    contagion = torch.stack(
        [pairwise_conflict(node_opinion, opinion) for opinion in relation_opinions],
        dim=0,
    ).mean(dim=0)
    # Group the pairwise conflicts before the mean so the tensor stays [B] whichever
    # order the caller used; this is also cheaper than materialising an R x R stack.
    # The mean of per-pair means is invariant to grouping only when R is constant,
    # which it is, so this is exact and not merely an approximation.
    pair_conflicts = [
        pairwise_conflict(relation_opinions[a], relation_opinions[b])
        for a in range(len(relation_opinions))
        for b in range(a + 1, len(relation_opinions))
    ]
    mutual = (
        torch.stack(pair_conflicts, dim=0).mean(dim=0)
        if pair_conflicts
        else torch.zeros_like(contagion)
    )

    fused = node_opinion
    for opinion, factor in zip(relation_opinions, discounts, strict=True):
        fused, _ = combine_opinions(fused, discount_opinion(opinion, factor))
    return fused, contagion, mutual
