import numpy as np
import pytest

from riskgnn.dataset_adapters.acra.preparation import prepare
from riskgnn.dataset_adapters.registry import inspect as validate
from riskgnn.workbench.artifacts import read_json, verify
from riskgnn.workbench.predictor import Predictor
from riskgnn.workbench.training import evaluate, train


def test_singapore_analysis_and_portable_profile(export_zip, tmp_path):
    validated, prepared, model = [tmp_path / name for name in ("validated", "prepared", "model")]
    result = validate(export_zip, validated)
    assert result["supportedRunnerIds"] == ["riskgnn"]
    assert result["analysis"]["totalRows"] == result["counts"]["company_attr"]
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
