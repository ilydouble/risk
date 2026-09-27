from __future__ import annotations

from pathlib import Path

from workbench.data import load_bundle
from workbench.demo import build_demo_bundle
from workbench.features import select_features
from workbench.profile import TrainingProfile, build_training_profile
from workbench.tabular import FittedVariant, TabularSuite
from workbench.training import _train


def test_training_profile_records_independent_dataset_training(tmp_path: Path) -> None:
    data = load_bundle(build_demo_bundle(tmp_path / "graph.zip", rows=180, include_graph=True))
    selection = select_features(data, mode="recommended", manual=[])
    metrics = {
        "rocAuc": 0.8,
        "prAuc": 0.7,
        "ks": 0.4,
        "brier": 0.18,
        "precision": 0.6,
        "recall": 0.7,
        "f1": 0.65,
        "threshold": 0.5,
        "confusion": {"truePositive": 7},
        "calibration": [],
    }
    variant = FittedVariant(
        "gnn_no_hyper",
        {
            "role": "riskgnn_configuration",
            "metrics": {"validation": metrics, "test": metrics},
        },
        b"model",
    )
    request = {
        "requested_models": ["gnn_no_hyper"],
        "feature_columns": [],
        "configuration": {
            "featureMode": "recommended",
            "seed": 19,
            "useEvents": True,
            "useRelations": True,
            "useHyperedges": False,
        },
    }

    profile = build_training_profile(
        data,
        request,
        TabularSuite(selection, [variant]),
        bundle_sha256="a" * 64,
        dataset_id="dataset-1",
        experiment_id="experiment-1",
    )
    payload = profile.model_dump(mode="json", by_alias=True)

    assert TrainingProfile.model_validate(payload) == profile
    assert payload["modelFamily"] == "RiskGNN-v1"
    assert payload["dataset"]["bundleSha256"] == "a" * 64
    assert payload["features"]["fitSplit"] == "train"
    assert payload["training"]["protocol"] == {
        "trainingScope": "current_dataset_only",
        "weightsTransferred": False,
        "externalPretrainedEmbeddings": False,
        "embeddingInitialization": "random",
        "preprocessingFitSplit": "train",
        "earlyStoppingSplit": "validation",
        "testUsedForSelection": False,
    }
    assert payload["graph"]["relations"]["rows"] > 0
    assert payload["evaluation"]["variants"][0]["name"] == "gnn_no_hyper"


def test_training_result_exposes_versioned_profile(tmp_path: Path) -> None:
    data = load_bundle(build_demo_bundle(tmp_path / "tabular.zip", rows=180))
    request = {
        "requested_models": ["logistic_regression"],
        "feature_columns": [],
        "configuration": {
            "featureMode": "recommended",
            "seed": 7,
            "useEvents": False,
            "useRelations": False,
            "useHyperedges": False,
        },
    }

    _, results = _train(
        data,
        request,
        bundle_sha256="b" * 64,
        dataset_id="dataset-2",
        experiment_id="experiment-2",
    )

    profile = results["trainingProfile"]
    assert profile["profileVersion"] == 1
    assert profile["datasetId"] == "dataset-2"
    assert profile["graph"]["enabled"] is False
    assert profile["encoding"]["nodes"]["enabled"] is False
    assert profile["evaluation"]["variants"][0]["name"] == "logistic_regression"
