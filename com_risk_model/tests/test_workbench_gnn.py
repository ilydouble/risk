from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import torch
from com_risk_runtime.model import RiskGNNCore

from workbench.data import load_bundle
from workbench.demo import build_demo_bundle
from workbench.features import select_features
from workbench.gnn import WorkbenchRiskGNN, prepare_graph_batch, train_gnn_variants
from workbench.tabular import TabularSuite
from workbench.training import _artifact


def test_event_relation_and_hypergraph_ablations_run(tmp_path: Path) -> None:
    data = load_bundle(build_demo_bundle(tmp_path / "graph.zip", rows=180, include_graph=True))
    selection = select_features(data, mode="recommended", manual=[])
    selected = selection.selected

    batch, _, _ = prepare_graph_batch(data, selected, use_events=True)
    variants = train_gnn_variants(
        data,
        selected,
        ["gnn_self_only", "gnn_no_hyper", "gnn_full"],
        use_events=True,
        seed=11,
        max_epochs=20,
        patience=4,
    )

    assert len(batch.event_node) > 0
    assert len(batch.hyper_node) > 0
    assert [variant.name for variant in variants] == [
        "gnn_self_only",
        "gnn_no_hyper",
        "gnn_full",
    ]
    for variant in variants:
        assert variant.artifact
        assert variant.result["configuration"]["fitSplit"] == "train"
        assert variant.result["configuration"]["seed"] == 11
        assert 0 <= variant.result["metrics"]["test"]["rocAuc"] <= 1

    model = WorkbenchRiskGNN(1, [], 1, [], 1, 1, 1, 1)
    assert isinstance(model.core, RiskGNNCore)

    artifact_path = tmp_path / "artifact.zip"
    artifact_path.write_bytes(_artifact(TabularSuite(selection, variants), {"variants": []}))
    with zipfile.ZipFile(artifact_path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert {item["path"] for item in manifest["artifacts"]} == {
            "models/gnn_self_only.pt",
            "models/gnn_no_hyper.pt",
            "models/gnn_full.pt",
        }
        assert {item["role"] for item in manifest["artifacts"]} == {
            "riskgnn_configuration"
        }
        full = torch.load(
            io.BytesIO(archive.read("models/gnn_full.pt")), weights_only=True
        )
        assert full["format"] == "workbench-riskgnn-v2"
        assert full["model"] == "RiskGNN-v1"


def test_gnn_fixed_seed_is_reproducible(tmp_path: Path) -> None:
    data = load_bundle(build_demo_bundle(tmp_path / "graph.zip", rows=180, include_graph=True))
    selected = select_features(data, mode="recommended", manual=[]).selected
    arguments = (data, selected, ["gnn_self_only"])

    first = train_gnn_variants(
        *arguments, use_events=True, seed=19, max_epochs=15, patience=4
    )[0]
    second = train_gnn_variants(
        *arguments, use_events=True, seed=19, max_epochs=15, patience=4
    )[0]

    assert first.result["metrics"] == second.result["metrics"]
