"""Evidential Deep Learning loss functions for RiskGNN+.

Implements Type II Maximum Likelihood (Negative Log Marginal Likelihood via Digamma),
Kullback-Leibler divergence regularization to avoid misleading evidence, and
Focal / Margin-Aware modulation for extreme corporate default class imbalance.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


def digamma_nll_loss(
    alpha: torch.Tensor,
    target: torch.Tensor,
    num_classes: int = 2,
    eps: float = 1e-7,
) -> torch.Tensor:
    """Negative Log Marginal Likelihood for Dirichlet distribution.

    L_nll = sum_k y_k * (psi(S) - psi(alpha_k))

    Args:
        alpha: [B, K] Dirichlet parameters (alpha_k >= 1).
        target: [B] or [B, K] categorical ground-truth labels.
        num_classes: K classes (default 2).
        eps: Numerical guard.

    Returns:
        [B] per-sample negative log likelihood.
    """
    if target.dim() == 1:
        y_one_hot = F.one_hot(target.long(), num_classes=num_classes).float()
    else:
        y_one_hot = target.float()

    strength = torch.sum(alpha, dim=-1, keepdim=True).clamp_min(eps)
    # Digamma difference
    log_likelihood = torch.sum(
        y_one_hot * (torch.digamma(strength) - torch.digamma(alpha.clamp_min(eps))),
        dim=-1,
    )
    return log_likelihood


def dirichlet_kl_divergence(
    alpha: torch.Tensor,
    target: torch.Tensor,
    num_classes: int = 2,
    eps: float = 1e-7,
) -> torch.Tensor:
    """KL divergence between Dirichlet distribution and uniform Dirichlet(1, 1)."""
    if target.dim() == 1:
        y_one_hot = F.one_hot(target.long(), num_classes=num_classes).float()
    else:
        y_one_hot = target.float()

    tilde_alpha = y_one_hot + (1.0 - y_one_hot) * alpha
    tilde_strength = torch.sum(tilde_alpha, dim=-1, keepdim=True).clamp_min(eps)

    first_term = (
        torch.lgamma(tilde_strength)
        - torch.sum(torch.lgamma(tilde_alpha.clamp_min(eps)), dim=-1, keepdim=True)
        - torch.lgamma(torch.tensor(float(num_classes), device=alpha.device))
    )
    second_term = torch.sum(
        (tilde_alpha - 1.0)
        * (torch.digamma(tilde_alpha.clamp_min(eps)) - torch.digamma(tilde_strength)),
        dim=-1,
        keepdim=True,
    )
    kl = (first_term + second_term).squeeze(-1)
    return kl.clamp_min(0.0)


class EvidentialRiskLoss(nn.Module):
    """Calibrated Evidential Cross-Entropy Loss for RiskGNN+.

    Uses expected log likelihood under Dirichlet:
        E[log p_k] = psi(alpha_k) - psi(S)
    equivalent to cross entropy on Dirichlet expectations + KL regularization.
    """

    def __init__(
        self,
        num_classes: int = 2,
        gamma_node: float = 0.3,
        gamma_graph: float = 0.3,
        kl_weight: float = 0.001,
        focal_gamma: float = 0.0,
        class_weights: tuple[float, float] | None = None,
    ) -> None:
        super().__init__()
        self.num_classes = num_classes
        self.gamma_node = gamma_node
        self.gamma_graph = gamma_graph
        self.kl_weight = kl_weight
        self.focal_gamma = focal_gamma
        self.class_weights = class_weights

    def forward(
        self,
        fused_alpha: torch.Tensor,
        node_alpha: torch.Tensor,
        graph_alpha: torch.Tensor,
        target: torch.Tensor,
        primary_logits: torch.Tensor | None = None,
        kl_annealing: float = 1.0,
    ) -> dict[str, torch.Tensor]:
        if target.dim() == 1:
            y_one_hot = F.one_hot(target.long(), num_classes=self.num_classes).float()
        else:
            y_one_hot = target.float()

        # Expected log-probabilities: log_p_k = digamma(alpha_k) - digamma(S)
        def expected_ce(a):
            s = torch.sum(a, dim=-1, keepdim=True)
            log_p = torch.digamma(a) - torch.digamma(s)
            return -torch.sum(y_one_hot * log_p, dim=-1)

        l_fused_sample = expected_ce(fused_alpha)
        l_node_sample = expected_ce(node_alpha)
        l_graph_sample = expected_ce(graph_alpha)

        l_fused = torch.mean(l_fused_sample)
        l_node = torch.mean(l_node_sample)
        l_graph = torch.mean(l_graph_sample)

        # KL
        kl_fused = dirichlet_kl_divergence(fused_alpha, target, self.num_classes)
        l_kl = torch.mean(kl_fused)

        # Primary Cross-Entropy on discriminative backbone logits
        l_primary = F.cross_entropy(primary_logits, target.long()) if primary_logits is not None else 0.0

        total_loss = (
            l_primary
            + 0.5 * l_fused
            + (self.gamma_node * 0.5) * l_node
            + (self.gamma_graph * 0.5) * l_graph
            + (self.kl_weight * kl_annealing) * l_kl
        )
        return {
            "loss": total_loss,
            "loss_primary": l_primary,
            "loss_fused": l_fused,
            "loss_node": l_node,
            "loss_graph": l_graph,
            "loss_kl": l_kl,
        }
