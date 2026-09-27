import csv
import io

import pytest

from risk_api.modules.modeling.analysis import AnalysisError, analyze_csv, train_baseline


def make_csv(rows: int = 80) -> bytes:
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["company_id", "debt_ratio", "lawsuit_count", "age", "defaulted"])
    for index in range(rows):
        risky = index % 4 == 0
        writer.writerow(
            [
                f"C{index:04d}",
                "" if index == 7 else 0.78 + index / 1000 if risky else 0.25 + index / 2000,
                3 + index % 3 if risky else index % 2,
                2 + index % 5 if risky else 8 + index % 12,
                1 if risky else 0,
            ]
        )
    return stream.getvalue().encode()


def test_analyze_csv_reports_quality_and_target_candidates() -> None:
    analysis, preview = analyze_csv(make_csv())

    assert analysis["rowCount"] == 80
    assert analysis["columnCount"] == 5
    assert analysis["missingCells"] == 1
    assert analysis["duplicateRows"] == 0
    assert {item["name"] for item in analysis["targetCandidates"]} == {"defaulted"}
    assert len(preview) == 8
    debt = next(column for column in analysis["columns"] if column["name"] == "debt_ratio")
    assert debt["kind"] == "numeric"
    assert debt["missingCount"] == 1


def test_train_baseline_is_deterministic_and_returns_holdout_metrics() -> None:
    arguments = (make_csv(), "defaulted", "1", ["debt_ratio", "lawsuit_count", "age"], 42)
    first = train_baseline(*arguments)
    second = train_baseline(*arguments)

    assert first == second
    assert first["configuration"]["evaluationScope"] == "quick_baseline_not_temporal_validation"
    assert first["configuration"]["trainRows"] == 64
    assert first["configuration"]["testRows"] == 16
    assert [item["feature"] for item in first["coefficients"]]
    for split in ("train", "test"):
        metrics = first["metrics"][split]
        assert 0 <= metrics["rocAuc"] <= 1
        assert 0 <= metrics["prAuc"] <= 1
        assert sum(metrics["confusion"].values()) == metrics["rows"]


def test_train_baseline_rejects_non_numeric_feature() -> None:
    with pytest.raises(AnalysisError, match="numeric"):
        train_baseline(make_csv(), "defaulted", "1", ["company_id"], 42)


def test_analyze_csv_rejects_too_few_rows() -> None:
    with pytest.raises(AnalysisError, match="at least 10"):
        analyze_csv(make_csv(rows=9))
