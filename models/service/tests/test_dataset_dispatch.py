import json

import numpy as np
import pytest

from riskgnn.dataset_adapters.registry import inspect as validate
from riskgnn.dataset_adapters.sg_comrisk.preparation import prepare
from riskgnn.tools.bundle_demo import build_demo_bundle
from riskgnn.workbench.artifacts import read_json, verify
from riskgnn.workbench.predictor import Predictor
from riskgnn.workbench.training import evaluate, train


def test_bundle_analysis_has_real_file_index_and_declared_capabilities(tmp_path):
    source = build_demo_bundle(tmp_path / "input.zip", rows=180, include_graph=True)
    result = validate(source, tmp_path / "validated")
    assert result["protocol"] == "bundle-v1"
    assert result["supportedRunnerIds"] == []
    assert result["analysis"]["totalRows"] == 180
    assert result["analysis"]["graph"]["connectedComponents"] == 3
    assert all(item["size"] > 0 and len(item["sha256"]) == 64 for item in result["files"])
    assert result["datasetProfile"]["taskType"] == "loan_application"
    json.dumps(result, allow_nan=False)


def test_singapore_analysis_and_portable_profile(export_zip, tmp_path):
    validated, prepared, model = [tmp_path / name for name in ("validated", "prepared", "model")]
    result = validate(export_zip, validated)
    assert result["supportedRunnerIds"] == ["riskgnn"]
    assert result["analysis"]["totalRows"] == 90
    assert len(result["analysis"]["drift"]) == 12
    prepare(validated, prepared)
    train(prepared, model, epochs=1, runner_id="riskgnn")
    evaluate(model)
    verify(model, "riskgnn-model-v2")
    meta = read_json(model / "metadata.json")
    assert meta["experimentProfile"]["runnerId"] == "riskgnn"
    assert meta["experimentProfile"]["graph"]["enabled"] is True
    assert len(np.load(model / "context.npz", allow_pickle=False)["edges"]) > 0
    ids = read_json(model / "ids.json")[:2]
    assert Predictor(model).predict(ids) == list(reversed(Predictor(model).predict(ids[::-1])))
    with pytest.raises(ValueError, match="Only RiskGNN"):
        train(prepared, tmp_path / "disabled", runner_id="riskgnn-plus")
