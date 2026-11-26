"""Raw-person propagation, missing-neighborhood and checkpoint contracts."""

import pytest
import torch
from riskgnn_pp import RiskGNNPlusPlus
from riskgnn_pp.person_attributes import PersonAttributeMeanEncoder
from smesd_uncertainty.comrisk_base.utils import build_incidence


def model(features=0):
    return RiskGNNPlusPlus(
        input_dim=16,
        output_dim=12,
        company_num=4,
        person_num=0,
        rel_num=1,
        cause_type_num=1,
        court_type_num=1,
        category_num=1,
        time_label_num=1,
        device=torch.device("cpu"),
        com_initial_emb=torch.zeros(4, 32),
        person_initial_emb=torch.empty(0, 32),
        n_company_attr_dims=2,
        hyper_impl="vectorized",
        hete_scalar_weights=False,
        person_attribute_dims=features,
    ).eval()


def inputs():
    return (
        {},
        torch.ones(4, 2),
        (
            torch.tensor([[0, 1], [1, 0], [1, 2], [2, 1]]),
            torch.zeros(4, dtype=torch.long),
            torch.ones(4),
        ),
        [build_incidence(4, {"g": [0, 1, 2]}) for _ in range(3)],
        torch.arange(4),
        torch.full((4, 1), 0.5),
    )


def test_duplicate_memberships_and_empty_companies():
    layer = PersonAttributeMeanEncoder(2, 3)
    attributes = torch.tensor([[1.0, 0.0], [0.0, 1.0]])
    edges = torch.tensor([[0, 0], [1, 0], [1, 1]])
    expected = layer(attributes, edges, 4)
    actual = layer(attributes, torch.cat((edges, edges[:1])), 4)
    assert torch.equal(expected, actual)
    assert torch.equal(actual[2:], torch.zeros(2, 3))
    with pytest.raises(ValueError, match="namespace"):
        layer(attributes, torch.tensor([[2, 0]]), 4)


def test_attributes_affect_graph_evidence_and_receive_gradient(tmp_path):
    torch.manual_seed(3)
    enhanced = model(42)
    args = inputs()
    attributes = torch.randn(3, 42, requires_grad=True)
    edges = torch.tensor([[0, 0], [1, 0], [1, 1]])
    before = enhanced(*args, person_attributes=attributes, person_company_edges=edges)
    changed = attributes.detach().clone()
    changed[0] += 1
    after = enhanced(*args, person_attributes=changed, person_company_edges=edges)
    assert torch.equal(before.node_embedding, after.node_embedding)
    assert not torch.equal(before.graph_embedding, after.graph_embedding)
    assert not torch.equal(before.fused_probabilities, after.fused_probabilities)
    unused = attributes.detach().clone()
    unused[2] += 100
    irrelevant = enhanced(*args, person_attributes=unused, person_company_edges=edges)
    assert torch.equal(before.fused_probabilities, irrelevant.fused_probabilities)
    (-before.fused_probabilities[:, 1].log().mean()).backward()
    assert attributes.grad[:2].abs().sum() > 0
    assert enhanced.person_attribute_encoder.encoder[0].weight.grad.abs().sum() > 0
    checkpoint = tmp_path / "model.pt"
    torch.save(enhanced.state_dict(), checkpoint)
    loaded = model(42)
    loaded.load_state_dict(torch.load(checkpoint, weights_only=True))
    reloaded = loaded(*args, person_attributes=attributes.detach(), person_company_edges=edges)
    assert torch.equal(before.fused_probabilities, reloaded.fused_probabilities)


def test_default_configuration_keeps_legacy_state_contract():
    legacy = model()
    assert not any("person_attribute_encoder" in k for k in legacy.state_dict())
    restored = model()
    restored.load_state_dict(legacy.state_dict(), strict=True)
    assert torch.equal(
        legacy(*inputs()).fused_probabilities, restored(*inputs()).fused_probabilities
    )
    with pytest.raises(ValueError, match="not configured"):
        legacy(
            *inputs(),
            person_attributes=torch.ones(1, 42),
            person_company_edges=torch.tensor([[0, 0]]),
        )


def test_node_route_isolates_person_attributes_from_graph_and_reloads(tmp_path):
    torch.manual_seed(3)
    enhanced = model(42)
    shared = {k: v.clone() for k, v in enhanced.state_dict().items()}
    rng = torch.random.get_rng_state().clone()
    enhanced.set_person_attribute_branch("node")
    assert torch.equal(rng, torch.random.get_rng_state())
    assert torch.equal(enhanced.final_proj[0].weight[:, :16], shared["final_proj.0.weight"])
    assert torch.count_nonzero(enhanced.final_proj[0].weight[:, 16:]) == 0
    with torch.no_grad():
        enhanced.final_proj[0].weight[:, 16:].normal_(std=0.1)
    args = inputs()
    attributes = torch.randn(3, 42, requires_grad=True)
    edges = torch.tensor([[0, 0], [1, 0], [1, 1]])
    before = enhanced(*args, person_attributes=attributes, person_company_edges=edges)
    changed = attributes.detach().clone()
    changed[0] += 1
    after = enhanced(*args, person_attributes=changed, person_company_edges=edges)
    assert torch.equal(before.graph_embedding, after.graph_embedding)
    assert not torch.equal(before.node_embedding, after.node_embedding)
    assert torch.equal(before.node_embedding[2:], after.node_embedding[2:])
    (-before.fused_probabilities[:, 1].log().mean()).backward()
    assert enhanced.person_attribute_encoder.encoder[0].weight.grad.abs().sum() > 0
    checkpoint = tmp_path / "node.pt"
    torch.save(enhanced.state_dict(), checkpoint)
    restored = model(42)
    restored.set_person_attribute_branch("node")
    restored.load_state_dict(torch.load(checkpoint, weights_only=True), strict=True)
    reloaded = restored(*args, person_attributes=attributes.detach(), person_company_edges=edges)
    assert torch.equal(before.fused_probabilities, reloaded.fused_probabilities)
