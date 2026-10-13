"""Contract tests for RiskGNN++ topology-aware evidence calibration.

These cover the subjective-logic invariants (mass + uncertainty == 1, discount
extremes, conflict range) and a forward/backward smoke test on a tiny synthetic
heterogeneous graph, so the analytical guarantees are checked without the datasets.
"""

from __future__ import annotations

import torch
from riskgnn_plus import EvidentialRiskLoss
from riskgnn_pp import (
    Opinion,
    RiskGNNPlusPlus,
    combine_opinions,
    discount_opinion,
    multi_source_combine,
    opinion_from_evidence,
    opinion_to_alpha,
    pairwise_conflict,
)
from riskgnn_pp.model import RiskGNNPlusPlusOutput
from smesd_uncertainty.comrisk_base.utils import build_incidence


def _opinion(mass0: float, mass1: float, uncertainty: float) -> Opinion:
    return Opinion(
        mass=torch.tensor([[mass0, mass1]], dtype=torch.float32),
        uncertainty=torch.tensor([uncertainty], dtype=torch.float32),
    )


def test_opinion_mass_and_uncertainty_sum_to_one():
    evidence = torch.tensor([[0.3, 5.0], [0.0, 0.0], [2.0, 2.0]])
    opinion = opinion_from_evidence(evidence)
    total = opinion.mass.sum(dim=-1) + opinion.uncertainty
    assert torch.allclose(total, torch.ones(3), atol=1e-6)


def test_opinion_alpha_roundtrip():
    evidence = torch.tensor([[0.3, 5.0], [2.0, 2.0]])
    alpha = evidence + 1.0
    recovered = opinion_to_alpha(opinion_from_evidence(evidence))
    assert torch.allclose(recovered, alpha, atol=1e-5)


def test_discount_is_identity_at_one_and_vacuous_at_zero():
    opinion = _opinion(0.3, 0.5, 0.2)
    identity = discount_opinion(opinion, torch.tensor([1.0]))
    assert torch.allclose(identity.mass, opinion.mass, atol=1e-6)
    assert torch.allclose(identity.uncertainty, opinion.uncertainty, atol=1e-6)

    killed = discount_opinion(opinion, torch.tensor([0.0]))
    assert torch.allclose(killed.mass, torch.zeros_like(killed.mass), atol=1e-6)
    assert torch.allclose(killed.uncertainty, torch.ones_like(killed.uncertainty), atol=1e-6)


def test_combination_invariants_and_conflict_range():
    first = _opinion(0.8, 0.1, 0.1)
    second = _opinion(0.1, 0.8, 0.1)
    fused, conflict = combine_opinions(first, second)
    total = fused.mass.sum(dim=-1) + fused.uncertainty
    assert torch.allclose(total, torch.ones(1), atol=1e-5)
    assert 0.0 <= float(conflict) < 1.0
    assert float(pairwise_conflict(first, second)) > 0.5


def test_vacuous_source_leaves_fused_unchanged():
    anchor = _opinion(0.7, 0.2, 0.1)
    vacuous = _opinion(0.0, 0.0, 1.0)
    fused, _ = combine_opinions(anchor, vacuous)
    assert torch.allclose(fused.mass, anchor.mass, atol=1e-5)
    assert torch.allclose(fused.uncertainty, anchor.uncertainty, atol=1e-5)


def test_multi_source_conflict_separates_contagion_from_mutual_noise():
    node = _opinion(0.9, 0.05, 0.05)
    # Two relations agree with each other (low mutual) but both contradict the node.
    relations = [_opinion(0.05, 0.9, 0.05), _opinion(0.05, 0.9, 0.05)]
    discounts = [torch.tensor([1.0]), torch.tensor([1.0])]
    fused, contagion, mutual = multi_source_combine(node, relations, discounts)
    assert float(contagion) > 0.7
    assert float(mutual) < 0.1
    assert torch.allclose(fused.mass.sum(dim=-1) + fused.uncertainty, torch.ones(1), atol=1e-5)


def _tiny_graph(num_nodes: int = 24, rel_num: int = 4, attr_dim: int = 3):
    torch.manual_seed(0)
    pairs, types, weights = [], [], []
    for node in range(num_nodes):
        for step in range(1, 4):
            target = (node + step) % num_nodes
            pairs.append((node, target))
            types.append((node + step) % rel_num)
            weights.append(1.0)
    edge_index = torch.tensor(pairs, dtype=torch.long)
    edge_type = torch.tensor(types, dtype=torch.long)
    edge_weight = torch.tensor(weights, dtype=torch.float32)
    groups = [
        {"g0": list(range(0, 8)), "g1": list(range(8, 16)), "g2": list(range(16, 24))},
        {"a": list(range(0, 12)), "b": list(range(12, 24))},
    ]
    hyper = [build_incidence(num_nodes, group) for group in groups]
    return edge_index, edge_type, edge_weight, hyper


def _build_model(use_topology_discount: bool, use_degree_likelihood: bool):
    num_nodes = 24
    com_emb = torch.randn(num_nodes, 32)
    return RiskGNNPlusPlus(
        input_dim=16,
        output_dim=12,
        company_num=num_nodes,
        person_num=0,
        rel_num=4,
        cause_type_num=1,
        court_type_num=1,
        category_num=1,
        time_label_num=1,
        device=torch.device("cpu"),
        com_initial_emb=com_emb,
        person_initial_emb=torch.zeros(0, 32),
        n_company_attr_dims=3,
        hyper_impl="vectorized",
        use_hypergraph=True,
        use_edgegraph=True,
        hete_scalar_weights=True,
        use_community_prior=True,
        use_topology_discount=use_topology_discount,
        use_degree_likelihood=use_degree_likelihood,
    )


def _forward(model, idx):
    edge_index, edge_type, edge_weight, hyper = _tiny_graph()
    attr = torch.randn(len(idx), 3)
    prior = torch.randn(len(idx), 1)
    return model({}, attr, (edge_index, edge_type, edge_weight), hyper, idx, prior)


def test_forward_backward_and_degree_regularisation():
    model = _build_model(use_topology_discount=True, use_degree_likelihood=True)
    idx = torch.arange(24)
    output = _forward(model, idx)
    assert isinstance(output, RiskGNNPlusPlusOutput)
    total = output.fused_probabilities.sum(dim=-1)
    assert torch.allclose(total, torch.ones(24), atol=1e-4)
    assert float(output.conflict.min()) >= 0.0 and float(output.conflict.max()) <= 1.0
    assert torch.all(output.degree >= 0)

    loss_fn = EvidentialRiskLoss()
    target = (idx % 2).long()
    loss = loss_fn(
        output.fused_alpha,
        output.node_alpha,
        output.graph_alpha,
        target,
        primary_logits=output.primary_logits,
    )["loss"]
    assert torch.isfinite(loss)
    loss.backward()
    grads = [parameter.grad for parameter in model.parameters() if parameter.grad is not None]
    assert grads and any(float(g.abs().sum()) > 0 for g in grads)


def test_degree_regularisation_only_shrinks_evidence():
    model = _build_model(use_topology_discount=True, use_degree_likelihood=True)
    idx = torch.arange(24)
    output = _forward(model, idx)
    # The budget multiplier is <= 1, so regularised evidence never exceeds raw
    # evidence; equality holds only for degree-0 nodes.
    assert torch.all(output.fused_alpha_regularized <= output.fused_alpha_raw + 1e-6)
