import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

from model_service.files import write_json
from riskgnn.dataset_adapters.sg_comrisk.preparation import prepare
from riskgnn.dataset_adapters.sg_comrisk.validation import validate
from riskgnn.workbench.artifacts import export_zip as pack
from riskgnn.workbench.artifacts import read_json, verify
from riskgnn.workbench.network import EdgeRiskGNN
from riskgnn.workbench.predictor import Predictor
from riskgnn.workbench.training import evaluate, train


def test_archive_train_reload_predict(export_zip, tmp_path):
    validated, prepared, model = [tmp_path / name for name in ("valid", "prepared", "model")]
    manifest = validate(export_zip, validated)
    assert manifest["counts"]["company_attr"] == 90
    profile = prepare(validated, prepared)
    assert profile["targetCount"] == 90
    train(prepared, model, epochs=1)
    ids = read_json(model / "ids.json")[:3]
    before = Predictor(model).predict(ids)
    assert evaluate(model, output=tmp_path / "report")["independentReload"] is True
    archive = tmp_path / "model.zip"
    pack(model, archive)
    separate = tmp_path / "independent"
    with zipfile.ZipFile(archive) as z:
        z.extractall(separate)
    after = Predictor(separate).predict(ids)
    assert np.allclose(
        [r["probability"] for r in before], [r["probability"] for r in after], atol=1e-7
    )
    assert Predictor(separate).predict(list(reversed(ids))) == list(reversed(after))
    with pytest.raises(KeyError):
        Predictor(separate).predict(["missing"])
    (separate / "weights.pt").write_bytes(b"damaged")
    with pytest.raises(ValueError):
        verify(separate, "riskgnn-model-v2")


def test_manifest_path_and_format_rejected(tmp_path):

    for manifest in (
        {"formatVersion": 99},
        {
            "formatVersion": 1,
            "kind": "riskgnn-model-v2",
            "files": {"../outside": {"size": 1, "sha256": "bad"}},
        },
    ):
        write_json(tmp_path / "manifest.json", manifest)
        with pytest.raises(ValueError):
            verify(tmp_path, "riskgnn-model-v2")


def test_overlapping_splits_rejected(export_zip, tmp_path):

    root = tmp_path / "source"
    split = pd.read_parquet(root / "splits_5seed.parquet")
    pd.concat([split, split.iloc[:1]]).to_parquet(root / "splits_5seed.parquet")
    with zipfile.ZipFile(export_zip, "w") as z:
        for file in root.iterdir():
            z.write(file, file.name)
    with pytest.raises(ValueError, match="Overlapping"):
        validate(export_zip, tmp_path / "validated")


def test_node_edge_forward_matches_research_reference():

    # Reference uses dev's full RiskGNN constructor followed by utils.Classifier.
    expected = read_json(Path(__file__).parent / "fixtures/node-edge-forward.json")
    torch.manual_seed(42)
    model = EdgeRiskGNN(6, 2).eval()
    features = torch.arange(36, dtype=torch.float32).reshape(6, 6) / 36
    nodes = torch.tensor([2, 0, 4, 1, 3, 5])
    edges = np.array([[0, 1], [1, 0], [2, 1], [3, 0], [4, 2], [5, 3]])
    types = np.array([0, 0, 1, 1, 0, 1])
    with torch.inference_mode():
        actual = model(features, nodes, edges, types, 3)
    assert torch.allclose(actual, torch.tensor(expected["logProbabilities"]), atol=1e-7)
