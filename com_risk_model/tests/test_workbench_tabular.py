from __future__ import annotations

from pathlib import Path

from workbench.data import load_bundle
from workbench.demo import build_demo_bundle
from workbench.features import graph_statistics, select_features
from workbench.tabular import train_tabular_suite


def test_recommended_selection_and_tabular_models_are_reproducible(tmp_path: Path) -> None:
    data = load_bundle(build_demo_bundle(tmp_path / "loan.zip", rows=240))
    first = train_tabular_suite(
        data,
        requested_models=["logistic_regression", "hist_gradient_boosting"],
        feature_mode="recommended",
        manual_features=[],
        seed=23,
    )
    second = train_tabular_suite(
        data,
        requested_models=["logistic_regression", "hist_gradient_boosting"],
        feature_mode="recommended",
        manual_features=[],
        seed=23,
    )

    assert first.selection.selected == second.selection.selected
    assert {variant.name for variant in first.variants} == {
        "logistic_regression",
        "hist_gradient_boosting",
    }
    for left, right in zip(first.variants, second.variants, strict=True):
        assert left.result["metrics"] == right.result["metrics"]
        assert left.artifact
        for split in ("validation", "test"):
            assert 0 <= left.result["metrics"][split]["rocAuc"] <= 1


def test_graph_statistics_and_hgb_use_training_only_neighbor_labels(tmp_path: Path) -> None:
    data = load_bundle(build_demo_bundle(tmp_path / "graph.zip", rows=240, include_graph=True))
    statistics = graph_statistics(data)
    selection = select_features(data, mode="recommended", manual=[])

    suite = train_tabular_suite(
        data,
        requested_models=["graph_stats_hgb"],
        feature_mode="recommended",
        manual_features=[],
        seed=42,
    )

    assert selection.configuration["fitSplit"] == "train"
    assert len(statistics) == len(data.samples)
    assert "graph_neighbor_risk_prior" in statistics
    assert suite.variants[0].name == "graph_stats_hgb"
