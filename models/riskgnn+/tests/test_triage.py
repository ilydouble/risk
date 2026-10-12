"""Contracts that protect the paired triage comparison from leakage and miscounting."""

import numpy as np
import pytest
from riskgnn_plus.conformal import ConformalRiskAuditor
from smesd_uncertainty.triage import (
    compare_triage,
    decision_metrics,
    fixed_budget_mask,
    validate_predictions,
)


def predictions():
    rng = np.random.default_rng(7)
    data = {"cal_ids": np.arange(40), "test_ids": np.arange(40, 60)}
    for split, n in [("cal", 40), ("test", 20)]:
        data[f"{split}_y"] = rng.integers(0, 2, n)
        data[f"plus_{split}_u"] = rng.random(n)
        for model in ("comrisk", "plus"):
            p = rng.random(n)
            data[f"{model}_{split}_p"] = np.column_stack([1 - p, p])
    return data


def test_conformal_uses_exact_order_statistic_and_infinite_small_sample_threshold():
    # n=4, epsilon=.4 => ceil(5*.6)=3, so select .3 rather than numpy's .4.
    p = np.array([[0.9, 0.1], [0.8, 0.2], [0.7, 0.3], [0.6, 0.4]])
    auditor = ConformalRiskAuditor(epsilon=0.4, beta=0)
    assert auditor.calibrate(p, np.zeros(4), np.zeros(4, dtype=int)) == pytest.approx(
        0.3
    )
    auditor.epsilon = 0.05
    assert np.isinf(auditor.calibrate(p, np.zeros(4), np.zeros(4, dtype=int)))
    result = auditor.audit(p, np.zeros(4), np.zeros(4, dtype=int))
    assert result.deferral_rate == 1
    assert result.empirical_coverage == 1


def test_selection_and_calibration_do_not_depend_on_test_labels():
    data = predictions()
    original = compare_triage(data)
    data["test_y"] = 1 - data["test_y"]
    changed = compare_triage(data)
    for a, b in zip(original, changed, strict=True):
        for key in (
            "auto_rate",
            "auto_count",
            "threshold",
            "approve_count",
            "reject_count",
            "review_rate",
            "empty_rate",
        ):
            assert a.get(key) == b.get(key)


def test_fixed_budgets_are_exact_and_ties_use_id():
    mask = fixed_budget_mask(np.ones(5), np.array([5, 4, 3, 2, 1]), 0.4)
    assert mask.tolist() == [False, False, True, True, True]
    assert not fixed_budget_mask(np.ones(5), np.arange(5), 1).any()
    assert fixed_budget_mask(np.ones(5), np.arange(5), 0).all()


def test_nonautomated_cases_and_class_specific_errors():
    y = np.array([1, 0, 1, 0])
    metrics = decision_metrics(
        y, np.array([0, 1, -1, -1]), np.array([True, True, False, False])
    )
    assert metrics["review_rate"] == 0.5
    assert metrics["approved_defaults"] == metrics["rejected_nondefaults"] == 1
    assert metrics["auto_risk"] == 1
    empty = decision_metrics(y, np.zeros(4), np.zeros(4, dtype=bool))
    assert empty["auto_accuracy"] is None
    assert empty["auto_risk"] is None


def test_prediction_contract_rejects_overlap_and_bad_probabilities():
    data = predictions()
    validate_predictions(data)
    data["test_ids"][0] = data["cal_ids"][0]
    with pytest.raises(ValueError, match="overlap"):
        validate_predictions(data)
    data = predictions()
    data["plus_test_p"][0] = [0.1, 0.1]
    with pytest.raises(ValueError, match="sum to one"):
        validate_predictions(data)


def test_training_split_removes_repeated_target_companies_before_calibration(tmp_path):
    import pandas as pd
    from smesd_uncertainty.triage_training import load_dataset

    ids = [[0, 1, 2], [2, 3, 4, 5], [1, 5, 6, 7]]
    pd.to_pickle(ids, tmp_path / "split_data_idx.pkl")
    pd.to_pickle((np.zeros((8, 32)), np.zeros((1, 32))), tmp_path / "meta_emb.pkl")
    for name, group in zip(("train", "validate", "test"), ids, strict=True):
        hyper = {key: {0: list(range(8))} for key in ("industry", "area", "qualify")}
        pd.to_pickle(
            (
                {},
                np.zeros((len(group), 3)),
                [[], [], []],
                hyper,
                np.zeros(len(group), dtype=int),
            ),
            tmp_path / f"{name}_data.pkl",
        )
    dataset = load_dataset(tmp_path, "deduplicated", 42)
    sets = [set(s["idx"]) for s in dataset["splits"].values()]
    for i, a in enumerate(sets):
        for b in sets[i + 1 :]:
            assert not a & b
    assert set(dataset["splits"]["test"]["idx"]) == {6, 7}


def test_matched_conformal_comparators_automate_exactly_the_same_count():
    rows = compare_triage(predictions())
    matched = [r for r in rows if r["protocol"] == "matched_evidence_cp_coverage"]
    assert len(matched) == 3
    assert len({r["auto_count"] for r in matched}) == 1


def test_published_id_overlap_requires_explicit_original_policy():
    data = predictions()
    data["test_ids"][0] = data["cal_ids"][0]
    with pytest.raises(ValueError, match="overlap"):
        compare_triage(data)
    data["split_policy"] = np.asarray("original")
    rows = compare_triage(data)
    assert rows
    assert all(row["n"] == len(data["test_y"]) for row in rows)
    data["split_policy"] = np.asarray("unknown")
    with pytest.raises(ValueError, match="Unknown split policy"):
        compare_triage(data)


def test_original_loader_preserves_all_published_indices_and_legacy_calibration_split(
    tmp_path,
):
    import pandas as pd
    from smesd_uncertainty.triage_training import load_dataset

    ids = [[0, 1, 2], [2, 3, 4, 5], [1, 5, 6, 7]]
    pd.to_pickle(ids, tmp_path / "split_data_idx.pkl")
    pd.to_pickle((np.zeros((8, 32)), np.zeros((1, 32))), tmp_path / "meta_emb.pkl")
    for name, group in zip(("train", "validate", "test"), ids, strict=True):
        hyper = {key: {0: list(range(8))} for key in ("industry", "area", "qualify")}
        pd.to_pickle(
            (
                {},
                np.zeros((len(group), 3)),
                [[], [], []],
                hyper,
                np.arange(len(group)) % 2,
            ),
            tmp_path / f"{name}_data.pkl",
        )
    dataset = load_dataset(tmp_path, "original", 42)
    splits = dataset["splits"]
    assert splits["train"]["idx"] == ids[0]
    assert splits["test"]["idx"] == ids[2]
    perm = np.random.RandomState(42).permutation(len(ids[1]))
    assert splits["cal"]["idx"] == [ids[1][i] for i in perm[:2]]
    assert splits["valid"]["idx"] == [ids[1][i] for i in perm[2:]]
    assert set(splits["cal"]["idx"]) | set(splits["valid"]["idx"]) == set(ids[1])
