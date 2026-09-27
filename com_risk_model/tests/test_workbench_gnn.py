from __future__ import annotations

from pathlib import Path

from workbench.data import load_bundle
from workbench.demo import build_demo_bundle
from workbench.features import select_features
from workbench.gnn import prepare_graph_batch, train_gnn_variants


def test_event_relation_and_hypergraph_ablations_run(tmp_path: Path) -> None:
    data = load_bundle(build_demo_bundle(tmp_path / "graph.zip", rows=180, include_graph=True))
    selected = select_features(data, mode="recommended", manual=[]).selected

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
        assert 0 <= variant.result["metrics"]["test"]["rocAuc"] <= 1


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
