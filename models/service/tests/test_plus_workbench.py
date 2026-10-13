"""Actual RiskGNN+ branches, isolated snapshots and portable reload on real inputs."""

from copy import deepcopy

import numpy as np
import pytest
import torch
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
        "smesd" if request.param == "smesd" else "uk-companies",
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
