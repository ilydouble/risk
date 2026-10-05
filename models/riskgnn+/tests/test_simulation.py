from __future__ import annotations

import numpy as np

from smesd_uncertainty import protocol, simulation


def test_extract_logical_pairs_requires_and_preserves_reverse_edges() -> None:
    graph = (
        [[0, 5], [5, 0], [1, 2], [2, 1]],
        [0, 1, 6, 7],
        [1.0, 1.0, 25.0, 25.0],
    )

    pairs = simulation.extract_logical_pairs(graph, company_count=5)

    assert pairs.source.tolist() == [0, 1]
    assert pairs.target.tolist() == [5, 2]
    assert pairs.relation.tolist() == [0, 6]
    assert pairs.strength.tolist() == [1.0, 25.0]


def test_observation_confidence_keeps_true_edges_and_marks_additions_low() -> None:
    clean = simulation.LogicalPairs(
        source=np.arange(100),
        target=np.arange(100, 200),
        relation=np.repeat([0, 2], 50),
        strength=np.full(100, 25.0, dtype=np.float32),
    )
    false = simulation.LogicalPairs(
        source=np.arange(20),
        target=np.arange(200, 220),
        relation=np.repeat([0, 2], 10),
        strength=np.ones(20, dtype=np.float32),
    )

    true_confidence, false_confidence = simulation.assign_observation_confidence(
        clean,
        false,
        rng=np.random.default_rng(14),
    )

    assert np.all(true_confidence == 1.0)
    assert np.all(false_confidence >= 0.05)
    assert np.all(false_confidence <= 0.2)
    assert np.unique(false_confidence).size > 2


def test_scenario_adds_full_noise_ratio_without_deleting_true_edges() -> None:
    clean = simulation.LogicalPairs(
        source=np.arange(100),
        target=np.arange(100, 200),
        relation=np.repeat([0, 2], 50),
        strength=np.full(100, 25.0, dtype=np.float32),
    )

    scenario = simulation.build_scenario(
        clean, noise_ratio=0.4, rng=np.random.default_rng(14)
    )

    assert int(scenario["is_true"].sum()) == 100
    assert int((~scenario["is_true"]).sum()) == 40
    assert len(scenario["source"]) == 140
    assert np.all(scenario["confidence"][scenario["is_true"]] == 1.0)
    assert np.all(scenario["strength"][~scenario["is_true"]] == 1.0)


def test_generated_false_pairs_have_neutral_strength() -> None:
    clean = simulation.LogicalPairs(
        source=np.arange(20),
        target=np.arange(100, 120),
        relation=np.repeat([0, 2], 10),
        strength=np.arange(1, 21, dtype=np.float32),
    )

    false = simulation.generate_false_pairs(
        clean, noise_ratio=0.4, rng=np.random.default_rng(14)
    )

    assert len(false) == 8
    assert np.all(false.strength == 1.0)


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


def test_metapath_edges_use_local_person_ids_at_exact_boundary() -> None:
    scenario = {
        "source": np.asarray([0, 4, 2]),
        "target": np.asarray([4, 1, 3]),
        "relation": np.asarray([0, 8, 6]),
        "strength": np.ones(3, dtype=np.float32),
        "confidence": np.asarray([1.0, 0.2, 0.5], dtype=np.float32),
        "is_true": np.asarray([True, False, True]),
    }

    edges = protocol.build_metapath_edges(
        {"train": scenario, "valid": scenario, "test": scenario},
        graph_mode="all",
        threshold=0.5,
        company_count=4,
        person_count=2,
    )

    assert edges[0].tolist() == [[0, 0]]
    assert edges[1].tolist() == [[0, 0]]
    assert edges[8].tolist() == [[0, 1]]
    assert edges[9].tolist() == [[1, 0]]
    assert edges[6].tolist() == [[2, 3]]
    assert edges[7].tolist() == [[3, 2]]


def test_embedding_graph_mode_matches_variant_topology() -> None:
    assert protocol.embedding_graph_mode("comrisk_oracle") == "oracle"
    assert protocol.embedding_graph_mode("comrisk_noisy") == "all"
    assert protocol.embedding_graph_mode("riskgnn_gated") == "all"
    assert protocol.embedding_graph_mode("riskgnn_filter") == "filter"
    assert protocol.embedding_spec("riskgnn_noisy") == ("all", "ignore")
    assert protocol.embedding_spec("riskgnn_embed") == ("all", "gate")
    assert protocol.embedding_spec("riskgnn_gated") == ("all", "gate")
    assert protocol.embedding_spec("riskgnn_shuffled") == ("all", "shuffle")


def test_metapath_graph_preserves_confidence_for_both_directions() -> None:
    scenario = {
        "source": np.asarray([0, 4]),
        "target": np.asarray([4, 1]),
        "relation": np.asarray([0, 8]),
        "strength": np.ones(2, dtype=np.float32),
        "confidence": np.asarray([0.2, 0.8], dtype=np.float32),
        "is_true": np.asarray([False, True]),
    }

    edges, confidence = protocol.build_metapath_graph(
        {"train": scenario},
        graph_mode="all",
        confidence_mode="gate",
        seed=14,
        threshold=0.5,
        company_count=4,
        person_count=2,
    )

    assert edges[0].tolist() == [[0, 0]]
    assert edges[1].tolist() == [[0, 0]]
    assert edges[8].tolist() == [[0, 1]]
    assert edges[9].tolist() == [[1, 0]]
    assert np.allclose(confidence[0], [0.2])
    assert np.allclose(confidence[1], [0.2])
    assert np.allclose(confidence[8], [0.8])
    assert np.allclose(confidence[9], [0.8])


def test_metapath_graph_uses_strongest_confidence_for_duplicate_edge() -> None:
    base = {
        "source": np.asarray([0]),
        "target": np.asarray([4]),
        "relation": np.asarray([0]),
        "strength": np.ones(1, dtype=np.float32),
        "is_true": np.asarray([True]),
    }
    first = {**base, "confidence": np.asarray([0.2], dtype=np.float32)}
    second = {**base, "confidence": np.asarray([0.8], dtype=np.float32)}

    _, confidence = protocol.build_metapath_graph(
        {"train": first, "valid": second},
        graph_mode="all",
        confidence_mode="gate",
        seed=14,
        threshold=0.5,
        company_count=4,
        person_count=2,
    )

    assert np.allclose(confidence[0], [0.8])
    assert np.allclose(confidence[1], [0.8])
