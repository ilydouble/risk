"""End-to-end unit and integration tests for RiskGNN+."""

import numpy as np
import pytest
import torch

from riskgnn_plus import (
    AuditDecision,
    ConformalRiskAuditor,
    EvidentialRiskLoss,
    RiskGNNPlus,
    analyze_conflict_contagion,
    compute_evidence_state,
    dempster_shafer_combine_binary,
    evaluate_risk_predictions,
    expected_calibration_error,
)


class TestDSTFusion:
    def test_mathematical_invariants(self):
        """Verify sum(m_k) + u == 1.0 identically for any valid inputs."""
        torch.manual_seed(42)
        node_evidence = torch.rand(100, 2) * 10.0
        graph_evidence = torch.rand(100, 2) * 10.0

        dst_out = dempster_shafer_combine_binary(node_evidence, graph_evidence)

        # 1. Node invariant: sum(m_node) + u_node == 1.0
        node_sum = dst_out.node_state.belief_mass.sum(dim=-1) + dst_out.node_state.uncertainty
        assert torch.allclose(node_sum, torch.ones_like(node_sum), atol=1e-5)

        # 2. Graph invariant: sum(m_graph) + u_graph == 1.0
        graph_sum = dst_out.graph_state.belief_mass.sum(dim=-1) + dst_out.graph_state.uncertainty
        assert torch.allclose(graph_sum, torch.ones_like(graph_sum), atol=1e-5)

        # 3. Fused invariant: sum(m_fused) + u_fused == 1.0
        fused_sum = dst_out.fused_state.belief_mass.sum(dim=-1) + dst_out.fused_state.uncertainty
        assert torch.allclose(fused_sum, torch.ones_like(fused_sum), atol=1e-5)

        # 4. Probabilities sum to 1.0
        prob_sum = dst_out.fused_state.probabilities.sum(dim=-1)
        assert torch.allclose(prob_sum, torch.ones_like(prob_sum), atol=1e-5)

    def test_uninformative_graph_degeneration(self):
        """When graph evidence -> 0 (u_graph -> 1), fused output degenerates to Node branch."""
        node_evidence = torch.tensor([[4.0, 1.0]])  # Node has strong normal evidence
        graph_evidence = torch.tensor([[0.0, 0.0]])  # Graph is completely uninformative

        dst_out = dempster_shafer_combine_binary(node_evidence, graph_evidence)

        # Graph uncertainty must be 1.0
        assert torch.isclose(dst_out.graph_state.uncertainty, torch.tensor(1.0), atol=1e-5)

        # Fused belief masses and probabilities should match Node state
        assert torch.allclose(
            dst_out.fused_state.belief_mass, dst_out.node_state.belief_mass, atol=1e-4
        )
        assert torch.allclose(
            dst_out.fused_state.probabilities, dst_out.node_state.probabilities, atol=1e-4
        )
        assert torch.allclose(
            dst_out.fused_state.uncertainty, dst_out.node_state.uncertainty, atol=1e-4
        )

    def test_conflict_detection(self):
        """When Node says normal and Graph says default with high confidence, C approaches 1."""
        node_evidence = torch.tensor([[100.0, 0.0]])  # strongly normal
        graph_evidence = torch.tensor([[0.0, 100.0]]) # strongly default

        dst_out = dempster_shafer_combine_binary(node_evidence, graph_evidence)

        # Conflict must be very high (> 0.90)
        assert dst_out.conflict[0].item() > 0.90


class TestEvidentialLoss:
    def test_loss_gradients_and_non_negative(self):
        """Evidential loss should be positive and provide valid gradients."""
        loss_fn = EvidentialRiskLoss(gamma_node=0.5, gamma_graph=0.5, kl_weight=0.1)

        fused_alpha = torch.tensor([[3.0, 1.5], [1.2, 4.0]], requires_grad=True)
        node_alpha = torch.tensor([[2.0, 1.2], [1.1, 3.5]], requires_grad=True)
        graph_alpha = torch.tensor([[2.5, 1.8], [1.5, 2.0]], requires_grad=True)
        targets = torch.tensor([0, 1])

        out = loss_fn(fused_alpha, node_alpha, graph_alpha, targets)
        loss = out["loss"]

        assert loss.item() > 0.0
        loss.backward()

        assert fused_alpha.grad is not None
        assert node_alpha.grad is not None
        assert graph_alpha.grad is not None


class TestConformalAuditor:
    def test_guaranteed_coverage(self):
        """On calibrated synthetic data, empirical test coverage must satisfy >= 1 - epsilon."""
        np.random.seed(42)
        n_samples = 2000

        # Synthetic probabilities and uncertainties
        probs_1 = np.random.beta(0.5, 5.0, size=n_samples) # skewed default probabilities
        probs = np.column_stack([1.0 - probs_1, probs_1])
        uncertainties = np.random.uniform(0.05, 0.4, size=n_samples)

        # Ground truth simulated from probabilities
        labels = (np.random.rand(n_samples) < probs_1).astype(int)

        cal_p, test_p = probs[:1000], probs[1000:]
        cal_u, test_u = uncertainties[:1000], uncertainties[1000:]
        cal_y, test_y = labels[:1000], labels[1000:]

        auditor = ConformalRiskAuditor(epsilon=0.10, beta=0.5)
        auditor.calibrate(cal_p, cal_u, cal_y)
        res = auditor.audit(test_p, test_u, test_y)

        # Theoretical guarantee: coverage >= 1 - epsilon (0.90) with small statistical slack
        assert res.empirical_coverage is not None
        assert res.empirical_coverage >= 0.88
        assert res.auto_decision_rate + res.deferral_rate + res.ood_rate == pytest.approx(1.0)

    def test_decision_mapping(self):
        """Check all 4 decisions: AUTO_APPROVE, AUTO_REJECT, HUMAN_REVIEW, OOD_ALERT."""
        auditor = ConformalRiskAuditor(epsilon=0.05, beta=0.2)
        auditor.conformal_threshold_ = 0.50

        # Sample 0: very confident normal -> C = {0} -> AUTO_APPROVE
        # Sample 1: very confident default -> C = {1} -> AUTO_REJECT
        # Sample 2: low confidence / balanced -> 1 - p + beta*u <= q_hat for both -> C = {0, 1} -> HUMAN_REVIEW
        # Sample 3: high penalty on both -> 1 - p + beta*u > q_hat for both -> C = {} -> OOD_ALERT
        # With q_hat = 0.55, beta = 0.1:
        # Sample 0: p=[0.95, 0.05], u=0.1 -> E = [0.05 + 0.01 = 0.06 (<=0.55), 0.95 + 0.01 = 0.96 (>0.55)] -> {0}
        # Sample 1: p=[0.05, 0.95], u=0.1 -> E = [0.96 (>0.55), 0.06 (<=0.55)] -> {1}
        # Sample 2: p=[0.50, 0.50], u=0.2 -> E = [0.50 + 0.02 = 0.52 (<=0.55), 0.50 + 0.02 = 0.52 (<=0.55)] -> {0, 1}
        # Sample 3: p=[0.10, 0.10], u=0.9 -> E = [0.90 + 0.09 = 0.99 (>0.55), 0.90 + 0.09 = 0.99 (>0.55)] -> {}
        auditor = ConformalRiskAuditor(epsilon=0.05, beta=0.1)
        auditor.conformal_threshold_ = 0.55

        test_probs = np.array([
            [0.95, 0.05],
            [0.05, 0.95],
            [0.50, 0.50],
            [0.10, 0.10],
        ])
        test_u = np.array([0.1, 0.1, 0.2, 0.9])

        res = auditor.audit(test_probs, test_u)
        assert res.decisions[0] == AuditDecision.AUTO_APPROVE
        assert res.decisions[1] == AuditDecision.AUTO_REJECT
        assert res.decisions[2] == AuditDecision.HUMAN_REVIEW
        assert res.decisions[3] == AuditDecision.OOD_ALERT


class TestRiskGNNPlusModel:
    def test_forward_pass_synthetic(self):
        """Instantiate RiskGNNPlus and run forward pass without throwing."""
        device = torch.device("cpu")
        num_companies = 20
        num_persons = 5
        input_dim = 16
        output_dim = 12

        com_emb = np.random.randn(num_companies, 32).astype(np.float32)
        per_emb = np.random.randn(num_persons, 32).astype(np.float32)

        model = RiskGNNPlus(
            input_dim=input_dim,
            output_dim=output_dim,
            company_num=num_companies,
            person_num=num_persons,
            rel_num=4,
            cause_type_num=3,
            device=device,
            com_initial_emb=com_emb,
            person_initial_emb=per_emb,
            court_type_num=2,
            category_num=2,
            time_label_num=2,
            use_hypergraph=False,
            use_edgegraph=True,
            use_community_prior=False,
        )

        company_attr = np.random.randn(num_companies, 3).astype(np.float32)
        risk_data = {i: [] for i in range(num_companies)}

        # Small 4-edge heterogeneous graph (shape: [num_edges, 2] so that .transpose(0, 1) becomes [2, num_edges])
        edge_index = torch.tensor([[0, 1], [1, 2], [2, 3], [3, 0]], dtype=torch.long)
        edge_type = torch.tensor([0, 1, 2, 3], dtype=torch.long)
        edge_weight = torch.tensor([1.0, 1.0, 1.0, 1.0], dtype=torch.float32)
        hete_graph = (edge_index, edge_type, edge_weight)

        idx = list(range(num_companies))
        output = model.forward(
            risk_data=risk_data,
            company_attr=company_attr,
            hete_graph=hete_graph,
            hyp_graph=None,
            idx=idx,
        )

        assert output.probabilities.shape == (num_companies, 2)
        assert output.fused_alpha.shape == (num_companies, 2)
        assert output.fused_uncertainty.shape == (num_companies,)
        assert output.conflict.shape == (num_companies,)
        assert torch.all(output.probabilities >= 0.0)
        assert torch.all(output.fused_uncertainty >= 0.0)
        assert torch.all(output.fused_uncertainty <= 1.0)
