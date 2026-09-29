from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


simulator = load_module("smesd_uncertainty_simulator", "simulate_smesd_uncertainty.py")
protocol = load_module("smesd_uncertainty_protocol", "uncertainty_protocol.py")


def test_extract_logical_pairs_requires_and_preserves_reverse_edges() -> None:
    graph = (
        [[0, 5], [5, 0], [1, 2], [2, 1]],
        [0, 1, 6, 7],
        [1.0, 1.0, 25.0, 25.0],
    )

    pairs = simulator.extract_logical_pairs(graph, company_count=5)

    assert pairs.source.tolist() == [0, 1]
    assert pairs.target.tolist() == [5, 2]
    assert pairs.relation.tolist() == [0, 6]
    assert pairs.strength.tolist() == [1.0, 25.0]


def test_calibrated_confidence_matches_registered_truth_rates() -> None:
    true_confidence, false_confidence = simulator.assign_calibrated_confidence(
        true_count=10_000,
        false_count=4_000,
        rng=np.random.default_rng(14),
    )

    for confidence in simulator.CONFIDENCE_LEVELS:
        true_count = int(np.isclose(true_confidence, confidence).sum())
        false_count = int(np.isclose(false_confidence, confidence).sum())
        empirical = true_count / (true_count + false_count)
        assert abs(empirical - float(confidence)) < 0.002
    assert np.isclose(true_confidence, 1.0).any()


def test_directed_graph_keeps_pairs_and_separates_confidence_from_strength() -> None:
    scenario = {
        "source": np.asarray([0, 1, 2]),
        "target": np.asarray([5, 6, 3]),
        "relation": np.asarray([0, 2, 6]),
        "strength": np.asarray([1.0, 1.0, 25.0], dtype=np.float32),
        "confidence": np.asarray([1.0, 0.2, 0.5], dtype=np.float32),
        "is_true": np.asarray([True, False, True]),
    }

    edge_index, edge_type, strength, confidence = protocol.build_directed_graph(
        scenario, "riskgnn_gated", seed=14, threshold=0.5
    )

    assert edge_index.tolist() == [
        [0, 5],
        [1, 6],
        [2, 3],
        [5, 0],
        [6, 1],
        [3, 2],
    ]
    assert edge_type.tolist() == [0, 2, 6, 1, 3, 7]
    assert strength.tolist() == [1.0, 1.0, 25.0, 1.0, 1.0, 25.0]
    assert np.allclose(confidence, [1.0, 0.2, 0.5, 1.0, 0.2, 0.5])


def test_controls_preserve_or_transform_confidence_as_registered() -> None:
    scenario = {
        "source": np.arange(8),
        "target": np.arange(20, 28),
        "relation": np.asarray([0, 0, 0, 0, 2, 2, 2, 2]),
        "strength": np.ones(8, dtype=np.float32),
        "confidence": np.asarray([0.05, 0.2, 0.5, 1.0] * 2, dtype=np.float32),
        "is_true": np.asarray([False, False, True, True] * 2),
    }

    oracle = protocol.build_directed_graph(
        scenario, "comrisk_oracle", seed=14, threshold=0.5
    )
    ignored = protocol.build_directed_graph(
        scenario, "comrisk_noisy", seed=14, threshold=0.5
    )
    filtered = protocol.build_directed_graph(
        scenario, "riskgnn_filter", seed=14, threshold=0.5
    )
    shuffled = protocol.build_directed_graph(
        scenario, "riskgnn_shuffled", seed=14, threshold=0.5
    )
    inverted = protocol.build_directed_graph(
        scenario, "riskgnn_inverted", seed=14, threshold=0.5
    )

    assert len(oracle[1]) == 8
    assert len(ignored[1]) == 16
    assert np.all(ignored[3] == 1)
    assert len(filtered[1]) == 8
    assert np.all(filtered[3] == 1)
    assert sorted(shuffled[3][:8].tolist()) == sorted(scenario["confidence"].tolist())
    assert np.allclose(
        inverted[3][:8], np.clip(1.05 - scenario["confidence"], 0.05, 1.0)
    )


def test_oracle_is_identical_when_candidate_rows_and_false_edges_change() -> None:
    first = {
        "source": np.asarray([2, 0, 3, 1]),
        "target": np.asarray([7, 5, 8, 6]),
        "relation": np.asarray([2, 0, 2, 0]),
        "strength": np.asarray([1.0, 1.0, 2.0, 1.0], dtype=np.float32),
        "confidence": np.asarray([0.5, 1.0, 0.2, 0.05], dtype=np.float32),
        "is_true": np.asarray([True, True, False, False]),
    }
    second = {name: values[::-1].copy() for name, values in first.items()}
    second["source"][0] = 99
    second["target"][0] = 100

    first_graph = protocol.build_directed_graph(first, "comrisk_oracle", 14, 0.5)
    second_graph = protocol.build_directed_graph(second, "comrisk_oracle", 14, 0.5)

    for first_array, second_array in zip(first_graph, second_graph, strict=True):
        np.testing.assert_array_equal(first_array, second_array)
