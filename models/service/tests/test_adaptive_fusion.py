"""Stable boundaries for optional graphs, missing values and frozen model versions."""

from copy import deepcopy

import numpy as np
import pytest
import torch
from riskgnn_plus.workbench.adaptive import ADAPTIVE_ARCHITECTURE, NormalizedHypergraph
from riskgnn_plus.workbench.network import PortablePlus

from riskgnn.workbench.configuration import descriptor_digest, resolve, validate_frozen


@pytest.fixture
def adaptive_inputs():
    features = ["assets", "assets_missing", "liabilities", "liabilities_missing"]
    meta = {
        "architecture": ADAPTIVE_ARCHITECTURE,
        "companyCount": 9,
        "features": features,
        "relations": ["parent"],
        "hyperedgeTypes": ["industry", "region"],
        "preprocessing": {
            "mean": [2, 0.5, 3, 0.5],
            "scale": [2, 0.5, 3, 0.5],
            "fillValues": [2, 0, 3, 0],
        },
    }
    context = {
        "features": np.tile(
            np.array([[1, -1, 2, -1], [-1, -1, 1, -1], [0, 1, 0, 1]], dtype=np.float32), (3, 1)
        ),
        "snapshots": np.repeat(["train", "valid", "test"], 3),
        "splits": np.repeat(["train", "val", "test"], 3),
        "edges": np.empty((0, 3)),
        "company_embedding": np.zeros((9, 32)),
        "person_embedding": np.zeros((0, 32)),
        "hyper_nodes_0": np.array([0, 1, 3, 4, 6, 7]),
        "hyper_groups_0": np.repeat(np.arange(3), 2),
        "hyper_nodes_1": np.array([], dtype=int),
        "hyper_groups_1": np.array([], dtype=int),
    }
    return meta, context


def test_isolated_observation_falls_back_to_node_and_dst_is_neutral(adaptive_inputs):
    meta, context = adaptive_inputs
    model = PortablePlus(meta, context, {}).eval()
    with torch.inference_mode():
        output = model([0, 1, 2])
        node_logits = model.core.primary_classifier(output.node_embedding)
        assert torch.equal(output.primary_logits[2], node_logits[2])
        assert torch.allclose(output.fused_probabilities[2], output.node_probabilities[2])
        assert torch.equal(output.graph_probabilities[2], torch.tensor([0.5, 0.5]))
        graph = model.graph("train")[0]
        assert graph.last_graph_weight[2] == 0
        assert torch.all((graph.last_graph_weight[:2] > 0) & (graph.last_graph_weight[:2] < 1))
        assert (output.primary_logits - node_logits).abs().max() <= 0.5


def test_missing_marker_suppresses_placeholder_and_eval_is_order_independent(adaptive_inputs):
    meta, context = adaptive_inputs
    context["features"][0, 1] = 1
    model = PortablePlus(meta, context, {}).eval()
    with torch.inference_mode():
        expected = model([0, 1, 2]).probabilities
        context["features"][0, 0] = 1e8
        assert torch.equal(expected, model([0, 1, 2]).probabilities)
        assert torch.equal(expected.flip(0), model([2, 1, 0]).probabilities)
        assert torch.equal(expected[:1], model([0]).probabilities)
    assert context["features"][0, 0] == 1e8, "Forward must not mutate prepared inputs"


def test_gate_and_graph_train_with_shared_parameters_and_snapshot_isolation(adaptive_inputs):
    meta, context = adaptive_inputs
    torch.manual_seed(3)
    model = PortablePlus(meta, context, {})
    output = model([0, 1, 2])
    torch.nn.functional.cross_entropy(output.primary_logits, torch.tensor([1, 0, 1])).backward()
    for parameter in (model.core.graph_gate[-1].weight, model.core.hypergnn.proj.weight):
        assert parameter.grad is not None and parameter.grad.abs().sum() > 0
        assert torch.isfinite(parameter.grad).all()
    model.eval()
    with torch.inference_mode():
        expected = model([0, 1, 2]).probabilities
        modified = deepcopy(context)
        modified["features"][3:] += 100
        isolated = PortablePlus(meta, modified, {}).eval()
        isolated.load_state_dict(model.state_dict())
        assert torch.equal(expected, isolated([0, 1, 2]).probabilities)


def test_hypergraph_scale_does_not_grow_with_duplicate_types():
    one = NormalizedHypergraph(2, 2, 1).eval()
    two = NormalizedHypergraph(2, 2, 2).eval()
    two.proj.load_state_dict(one.proj.state_dict())
    group = (torch.tensor([0, 1]), torch.tensor([0, 0]), 1)
    x = torch.tensor([[1.0, -1.0], [3.0, 2.0], [0.0, 0.0]])
    assert torch.allclose(one(x, [group]), two(x, [group, group]))


def test_new_uk_default_is_explicit_and_old_frozen_runs_remain_legacy():
    contract = {
        "contract_version": 1,
        "dataset": {"id": "uk-companies", "version": "research"},
        "adapter": {"id": "uk-dataset-v1", "version": "2", "config": {"target_count": 60}},
    }
    configured = resolve(contract, {})
    assert configured["resolvedParameters"]["fusion"] == "adaptive"
    assert validate_frozen(contract, configured["resolvedParameters"], configured) == configured
    assert resolve(contract, {"fusion": "legacy"})["resolvedParameters"]["fusion"] == "legacy"
    old = deepcopy(configured)
    old["resolvedParameters"].pop("fusion")
    old["defaultParameters"].pop("fusion")
    old["parameterSchema"]["properties"].pop("fusion")
    old["parameterSchema"]["required"].remove("fusion")
    old["uiSchema"]["fields"] = [f for f in old["uiSchema"]["fields"] if f["path"] != "fusion"]
    old["schemaDigest"] = descriptor_digest(old)
    assert validate_frozen(contract, old["resolvedParameters"], old) == old
