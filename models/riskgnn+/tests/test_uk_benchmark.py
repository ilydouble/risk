"""Contract tests for the torch-free UK benchmark loader."""

from __future__ import annotations

import json

import numpy as np
import pytest
from uk_benchmark.data import load_uk_benchmark


def _snapshot(name: str, nodes: list[dict], edges: list[dict], hyperedges: list[dict]) -> dict:
    return {
        "schema_version": 1,
        "name": name,
        "synthetic": False,
        "evaluation": "isolated_snapshots",
        "feature_names": ["age_months", "n_charges"],
        "relation_names": ["SAME_ADDRESS", "EQUITY"],
        "hyperedge_types": ["sic_section", "postcode_area"],
        "nodes": nodes,
        "edges": edges,
        "hyperedges": hyperedges,
        "events": [],
    }


def _node(node_id: str, community: str, features: list[float], label: int, split: str) -> dict:
    return {
        "id": node_id,
        "kind": "company",
        "community": community,
        "features": features,
        "label": label,
        "split": split,
    }


@pytest.fixture()
def uk_dir(tmp_path):
    train = _snapshot(
        "UK-train",
        [
            _node("t0", "A", [12.0, 0.0], 0, "train"),
            _node("t1", "A", [24.0, 3.0], 1, "train"),
            _node("t2", "B", [36.0, 7.0], 0, "train"),
        ],
        [
            {"source": "t0", "target": "t1", "relation": "SAME_ADDRESS", "weight": 0.4},
            {"source": "t1", "target": "t2", "relation": "EQUITY", "weight": 1.0},
        ],
        [
            {"kind": "sic_section", "members": ["t0", "t2"]},
            {"kind": "postcode_area", "members": ["t0", "t1"]},
        ],
    )
    valid = _snapshot(
        "UK-valid",
        [
            _node("v0", "A", [6.0, 1.0], 0, "valid"),
            _node("v1", "B", [18.0, 5.0], 1, "valid"),
            _node("v2", "B", [30.0, 9.0], 0, "valid"),
            _node("v3", "A", [42.0, 11.0], 1, "valid"),
        ],
        [{"source": "v0", "target": "v3", "relation": "SAME_ADDRESS", "weight": 0.31}],
        [{"kind": "sic_section", "members": ["v0", "v2"]}],
    )
    test = _snapshot(
        "UK-test",
        [
            _node("e0", "A", [9.0, 2.0], 0, "test"),
            _node("e1", "B", [21.0, 4.0], 1, "test"),
            _node("e2", "B", [33.0, 6.0], 0, "test"),
        ],
        [{"source": "e1", "target": "e2", "relation": "SAME_ADDRESS", "weight": 0.75}],
        [{"kind": "sic_section", "members": ["e1", "e2"]}],
    )
    for name, payload in (("train", train), ("valid", valid), ("test", test)):
        (tmp_path / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")
    return tmp_path


def test_global_universe_and_split_partition(uk_dir):
    dataset = load_uk_benchmark(uk_dir)
    assert dataset["company_num"] == 10
    assert sorted(dataset["node_ids"]) == sorted(
        ["t0", "t1", "t2", "v0", "v1", "v2", "v3", "e0", "e1", "e2"]
    )
    train_idx = set(dataset["splits"]["train"]["idx"].tolist())
    valid_idx = set(dataset["splits"]["valid"]["idx"].tolist())
    cal_idx = set(dataset["splits"]["cal"]["idx"].tolist())
    test_idx = set(dataset["splits"]["test"]["idx"].tolist())
    assert len(train_idx) == 3 and len(test_idx) == 3
    assert valid_idx | cal_idx == set(range(3, 7))
    assert valid_idx & cal_idx == set()
    assert not (train_idx & test_idx)


def test_feature_transform_is_train_fit(uk_dir):
    dataset = load_uk_benchmark(uk_dir)
    # n_charges is a count column: log1p then z-scored against the train split.
    raw = np.log1p(np.asarray([0.0, 3.0, 7.0]))
    expected = (raw - raw.mean()) / raw.std()
    np.testing.assert_allclose(dataset["splits"]["train"]["attr"][:, 1], expected, rtol=1e-5)
    # age_months is left raw and also z-scored; train column is centred.
    assert abs(float(dataset["splits"]["train"]["attr"][:, 0].mean())) < 1e-5


def test_edges_stay_inside_snapshot_and_keep_weights(uk_dir):
    dataset = load_uk_benchmark(uk_dir)
    graph = dataset["splits"]["test"]["graph"]
    assert graph[0].shape == (1, 2)
    assert graph[1].tolist() == [0]
    assert graph[2].tolist() == pytest.approx([0.75])
    # valid and calibration reuse the valid snapshot graph.
    assert np.array_equal(
        dataset["splits"]["valid"]["graph"][0], dataset["splits"]["cal"]["graph"][0]
    )


def test_uniform_weights_override(uk_dir):
    dataset = load_uk_benchmark(uk_dir, uniform_weights=True)
    for name in ("train", "valid", "cal", "test"):
        weights = dataset["splits"][name]["graph"][2]
        assert np.allclose(weights, 1.0)


def test_hyperedge_kinds_are_separated(uk_dir):
    dataset = load_uk_benchmark(uk_dir)
    assert dataset["hyperedge_kinds"] == ["sic_section", "postcode_area"]
    kinds = dataset["hypergraphs"]["train"]
    assert len(kinds) == 2
    assert len(kinds[0]) == 1  # one sic_section group
    assert len(kinds[1]) == 1  # one postcode_area group


def test_max_nodes_subsamples_and_filters(uk_dir):
    dataset = load_uk_benchmark(uk_dir, max_nodes=2)
    assert dataset["company_num"] <= 6
    for name in ("train", "valid", "cal", "test"):
        idx = dataset["splits"][name]["idx"]
        assert dataset["splits"][name]["attr"].shape[0] == len(idx)
        graph = dataset["splits"][name]["graph"][0]
        if len(graph):
            assert set(graph.reshape(-1).tolist()) <= set(idx.tolist())


def test_missing_snapshot_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_uk_benchmark(tmp_path)
