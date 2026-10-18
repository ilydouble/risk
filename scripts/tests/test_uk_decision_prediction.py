"""Local prediction must keep the frozen input template and exclude supervision."""

import json
from copy import deepcopy

import pytest

from model_service.modules.decision.calibration import calibrated
from model_service.modules.decision.contracts.input import input_state
from model_service.modules.decision.prediction_cli import read_input
from scripts.prepare_uk_decisions import QUESTION, QUESTION_ID


def test_supervision_is_never_serialized_and_observed_values_are_preserved():
    row = {
        "state": {"features": {"cash": 0, "equity": -1000, "financial_currency": "GBP"}},
        "questions": {QUESTION_ID: QUESTION},
        "expected": {QUESTION_ID: "event"},
        "sample_id": "not-a-feature",
    }
    encoded = input_state(row)
    changed = deepcopy(row)
    changed["expected"][QUESTION_ID] = "no_event"
    assert input_state(changed) == encoded
    assert json.loads(encoded) == row["state"]
    assert "expected" not in encoded and "sample_id" not in encoded


@pytest.mark.parametrize("feature", ["label", "company_id", "cash_missing", "event_date"])
def test_undeclared_features_are_rejected(feature):
    with pytest.raises(ValueError, match="allowlist"):
        input_state({"state": {"features": {feature: 1}}})


def test_invalid_values_and_changed_questions_are_rejected():
    for features in ({"cash": None}, {"equity": float("nan")}, {"cash": "0"}):
        with pytest.raises(ValueError):
            input_state({"state": {"features": features}})
    with pytest.raises(ValueError, match="template"):
        input_state({"state": {"features": {}}, "questions": {"other": {}}})


def test_jsonl_selects_one_original_row_without_reading_other_rows(tmp_path):
    path = tmp_path / "input.jsonl"
    path.write_text('{"state": {"features": {}}}\n{"state": {"features": {"cash": 0}}}\n')
    assert read_input(path, 2)["state"]["features"] == {"cash": 0}
    with pytest.raises(ValueError, match="does not exist"):
        read_input(path, 3)


def test_jsonl_rejects_oversized_preceding_lines(tmp_path):
    path = tmp_path / "input.jsonl"
    path.write_text(" " * (1024 * 1024 + 1) + '\n{"state": {"features": {}}}\n')
    with pytest.raises(ValueError, match="exceeds"):
        read_input(path, 2)


def test_calibration_is_explicit_finite_and_preserves_candidate_order():
    assert calibrated([0.8, 0.2], 1) == pytest.approx([0.8, 0.2])
    result = calibrated([0.8, 0.2], 2)
    assert sum(result) == pytest.approx(1) and 0.2 < result[1] < 0.5
    for temperature in (0, -1, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="temperature"):
            calibrated([0.8, 0.2], temperature)
