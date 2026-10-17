"""Actual RiskGNN+ branches, isolated snapshots and portable reload on real inputs."""

from copy import deepcopy

import numpy as np
import pytest
import torch
from riskgnn_plus.workbench.explanation import explain
from riskgnn_plus.workbench.network import PortablePlus
from riskgnn_plus.workbench.preparation import FORMAT, prepare
from riskgnn_plus.workbench.training import train

from riskgnn.dataset_adapters.packaging import package
from riskgnn.dataset_adapters.registry import inspect, resolve
from riskgnn.workbench.artifacts import asset_digest, read_json
from riskgnn.workbench.configuration import ConfigurationError, descriptor_digest, validate_frozen
from riskgnn.workbench.configuration import resolve as configure
from riskgnn.workbench.predictor import Predictor
from riskgnn.workbench.training import evaluate


@pytest.fixture(params=["acra", "smesd", "uk"])
def plus_source(request, export_zip, datasets, tmp_path):
    if request.param == "acra":
        return export_zip
    source = datasets / ("comrisk_export_v5/smesd" if request.param == "smesd" else "uk_dataset_v1")
    archive = tmp_path / "plus.zip"
    package(
        source,
        archive,
        "smesd" if request.param == "smesd" else "uk-companies-legacy",
        "plus-test",
        overrides={"target_count": 60},
    )
    return archive


def test_real_plus_hypergraph_gradients_isolation_and_independent_reload(plus_source, tmp_path):
    inspect(plus_source, tmp_path / "validated")
    adapter, _ = resolve(plus_source)
    meta = prepare(adapter, tmp_path / "validated", tmp_path / "prepared", {"target_count": 60})
    assert meta["algorithm"] == "RiskGNN+"
    assert meta["hyperedgeCount"] > 0
    assert "hyperedges" in meta["usedInputs"]
    context = dict(np.load(tmp_path / "prepared/context.npz", allow_pickle=False))
    events = read_json(tmp_path / "prepared/risk_events.json")
    targets = np.where(context["splits"] == "train")[0].tolist()
    model = PortablePlus(meta, context, events)
    model(targets).primary_logits.sum().backward()
    gradient = model.core.hypergnn.proj.weight.grad
    assert gradient is not None and torch.isfinite(gradient).all() and gradient.abs().sum() > 0
    before_hyper = model.core.hypergnn.proj.weight.detach().clone()
    if meta["edgeCount"]:
        assert any(
            parameter.grad is not None
            and torch.isfinite(parameter.grad).all()
            and parameter.grad.abs().sum() > 0
            for parameter in model.core.hetegnn.parameters()
        ), "Directed graph layers must receive gradients"
    torch.optim.Adam(model.parameters(), lr=0.01).step()
    assert not torch.equal(before_hyper, model.core.hypergnn.proj.weight)
    if adapter.id == "smesd":
        assert events and meta["eventCount"] > 0 and "risk_events" in meta["usedInputs"]
        assert model.core.riskinfo.proj.weight.grad is not None
    model.eval()
    with torch.inference_mode():
        expected = model(targets).probabilities
        graph_model = model.graph(str(context["snapshots"][targets[0]]))[0]
        graph_model.use_hypergraph = False
        without = model(targets).probabilities
        assert not torch.allclose(expected, without, atol=1e-7), "Hyperedges must affect forward"
        graph_model.use_hypergraph = True
        if adapter.id != "sg-comrisk":
            modified = deepcopy(context)
            modified["features"][context["snapshots"] != "train"] += 100
            isolated = PortablePlus(meta, modified, events).eval()
            isolated.load_state_dict(model.state_dict())
            assert torch.allclose(expected, isolated(targets).probabilities, atol=1e-7)
    trained = train(tmp_path / "prepared", tmp_path / "model", 1)
    assert trained["algorithm"] == "RiskGNN+"
    assert trained["experimentProfile"]["artifactFormat"] == FORMAT
    model_dir = tmp_path / "model"
    before = asset_digest(model_dir)
    report = evaluate(model_dir, output=tmp_path / "report")
    assert report["algorithm"] == "RiskGNN+" and report["independentReload"]
    assert asset_digest(model_dir) == before
    predictor = Predictor(model_dir)
    ids = list(predictor.index)[:3]
    result = predictor.predict(ids)
    frozen_features = predictor.context["features"].copy()
    explanation = explain(predictor, ids[0])
    assert explanation["referenceSplit"] == "train"
    assert {item["feature"] for item in explanation["features"]} == set(meta["features"])
    assert all(np.isfinite(item["delta"]) for item in explanation["features"])
    assert np.array_equal(predictor.context["features"], frozen_features)
    assert predictor.predict(ids) == result
    item = explanation["features"][0]
    assert item["delta"] == pytest.approx(result[0]["probability"] - item["probabilityAtReference"])
    assert asset_digest(model_dir) == before, "Explanation must not change model artifacts"
    reordered = predictor.predict(ids[::-1])
    assert result == reordered[::-1]
    for row in result:
        assert all(
            0 <= row[key] <= 1
            for key in ("probability", "fusedProbability", "uncertainty", "conflict")
        )
    with pytest.raises(KeyError, match="Unknown bound-graph"):
        predictor.predict(["unseen-company"])


def test_plus_configuration_explicitly_rejects_previous_algorithm():
    contract = {
        "contract_version": 1,
        "dataset": {"id": "test", "version": "1"},
        "adapter": {"id": "smesd", "version": "1", "config": {}},
    }
    configured = configure(contract, {"epochs": 1})
    assert configured["resolvedParameters"]["algorithm"] == "riskgnn-plus"
    assert validate_frozen(contract, configured["resolvedParameters"], configured) == configured
    with pytest.raises(ConfigurationError):
        configure(contract, {"algorithm": "riskgnn"})

    legacy = deepcopy(configured)
    legacy["defaultParameters"].pop("algorithm")
    legacy["resolvedParameters"].pop("algorithm")
    legacy["parameterSchema"]["properties"].pop("algorithm")
    legacy["parameterSchema"]["required"].remove("algorithm")
    legacy["schemaDigest"] = descriptor_digest(legacy)
    with pytest.raises(ConfigurationError, match="previous RiskGNN") as retired:
        validate_frozen(contract, legacy["resolvedParameters"], legacy)
    assert retired.value.stale


def test_explanation_restores_feature_inputs_on_failure():
    from types import SimpleNamespace

    context = {"features": np.array([[1.0], [3.0], [5.0]], dtype=np.float32),
               "splits": np.array(["train", "train", "test"])}
    before = context["features"].copy()
    calls = 0

    def failing_model(nodes):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise RuntimeError("intervention failed")
        return SimpleNamespace(probabilities=torch.tensor([[0.5, 0.5]]))

    predictor = SimpleNamespace(
        context=context, index={"c": 2}, model=failing_model,
        meta={"features": ["age"], "preprocessing": {}, "sourceSha256": "a" * 64},
    )
    with pytest.raises(RuntimeError, match="intervention failed"):
        explain(predictor, "c")
    assert np.array_equal(before, context["features"])


def test_explanation_reference_uses_training_targets_only():
    from types import SimpleNamespace

    context = {"features": np.array([[1.0], [3.0], [100.0]], dtype=np.float32),
               "splits": np.array(["train", "train", "test"])}

    def model(nodes):
        probability = torch.sigmoid(torch.tensor(context["features"][nodes, 0]))
        return SimpleNamespace(probabilities=torch.stack((1 - probability, probability), dim=1))

    predictor = SimpleNamespace(
        context=context, index={"c": 2}, model=model,
        meta={"features": ["age"], "preprocessing": {}, "sourceSha256": "a" * 64},
    )
    result = explain(predictor, "c")
    item = result["features"][0]
    assert result["referenceCount"] == 2
    assert item["value"] == 100 and item["referenceValue"] == 2
    assert item["probabilityAtReference"] == pytest.approx(float(torch.sigmoid(torch.tensor(2.0))))
    assert item["delta"] > 0


def test_explanation_skips_unchanged_interventions_but_preserves_all_features():
    from types import SimpleNamespace

    context = {
        "features": np.array([[1.0, 2.0], [3.0, 2.0], [2.0, 5.0]], dtype=np.float32),
        "splits": np.array(["train", "train", "test"]),
    }
    original = context["features"].copy()
    calls = []

    def model(nodes):
        calls.append(context["features"][nodes].copy())
        probability = torch.sigmoid(torch.tensor(context["features"][nodes].sum(axis=1)))
        return SimpleNamespace(probabilities=torch.stack((1 - probability, probability), dim=1))

    predictor = SimpleNamespace(
        context=context, index={"c": 2}, model=model,
        meta={"features": ["unchanged", "changed"], "preprocessing": {},
              "sourceSha256": "a" * 64},
    )
    result = explain(predictor, "c")
    assert len(calls) == 2, "Only baseline and genuinely changed input need model execution"
    features = {row["feature"]: row for row in result["features"]}
    assert set(features) == {"unchanged", "changed"}
    assert features["unchanged"]["delta"] == 0
    assert features["changed"]["delta"] > 0
    assert np.array_equal(context["features"], original)
