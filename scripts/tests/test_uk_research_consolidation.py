"""A consolidated feature table must preserve each original observation and label."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from consolidate_uk_research import verify_observations  # noqa: E402
from isolate_uk_graph_labels import write_csv  # noqa: E402


def fixture_tables(tmp_path):
    graph, history = tmp_path / "graph", tmp_path / "history"
    graph.mkdir()
    history.mkdir()
    original = {"sample_id": "s1", "company_id": "00000001", "assets": "100"}
    write_csv(graph / "features.csv", [original], list(original))
    extended = {**original, "assets_previous": "80"}
    write_csv(history / "features.csv", [extended], list(extended))
    for directory in (graph, history):
        (directory / "labels.csv").write_text("sample_id,label\ns1,1\n")
    return graph, history, extended


def test_financial_extensions_preserve_observation_identity_and_baseline_values(tmp_path):
    graph, history, _ = fixture_tables(tmp_path)
    assert verify_observations(graph, history) == 1


def test_consolidation_rejects_changed_baseline_value(tmp_path):
    graph, history, extended = fixture_tables(tmp_path)
    write_csv(history / "features.csv", [{**extended, "assets": "999"}], list(extended))
    with pytest.raises(AssertionError):
        verify_observations(graph, history)


def test_consolidation_rejects_different_labels(tmp_path):
    graph, history, _ = fixture_tables(tmp_path)
    (history / "labels.csv").write_text("sample_id,label\ns1,0\n")
    with pytest.raises(AssertionError):
        verify_observations(graph, history)
