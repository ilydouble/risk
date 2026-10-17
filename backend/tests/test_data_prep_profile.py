import pytest

from risk_api.errors import AppError
from risk_api.modules.data_prep.profile import inspect_csv


def test_inspect_csv_keeps_identifier_and_reports_missing_and_duplicates() -> None:
    result = inspect_csv(
        "企业编号,营业收入,不良状态\n0012,100,1\n0012,100,1\n0034,未知,0\n".encode()
    )

    assert result["rowCount"] == 3
    assert result["duplicateRows"] == 1
    assert result["sampleRows"][0]["企业编号"] == "0012"
    assert result["fields"][1]["missingCount"] == 1
    assert result["fields"][2]["distinctCount"] == 2
    assert result["labelCandidates"][0]["field"] == "不良状态"
    assert result["labelCandidates"][0]["minorityShare"] == 0.333


def test_inspect_csv_rejects_extra_cells() -> None:
    with pytest.raises(AppError) as caught:
        inspect_csv(b"id,label\n1,0,extra\n")

    assert caught.value.code == "DATA_PREP_ROW_INVALID"


def test_inspect_csv_rejects_duplicate_headers() -> None:
    with pytest.raises(AppError) as caught:
        inspect_csv(b"id,id\n1,2\n")

    assert caught.value.code == "DATA_PREP_HEADER_DUPLICATE"


def test_inspect_csv_reports_dirty_values_and_candidate_keys() -> None:
    rows = [
        ("001", " 1 ", "2024-01-01", "A"),
        ("001", "1", "2024-01-02", "A"),
        ("002", "1", "2024-01-03", "B"),
        ("003", "2", "2024-01-04", "A"),
        ("004", "2", "2024-01-05", "B"),
        ("005", "2", "2024-01-06", "A"),
        ("006", "3", "2024-01-07", "B"),
        ("007", "100", "2024-01-08", "A"),
        ("008", "bad", "not-a-date", "B"),
    ]
    content = "company_id,amount,as_of,category\n" + "".join(",".join(row) + "\n" for row in rows)
    profile = inspect_csv(content.encode())
    fields = {field["name"]: field for field in profile["fields"]}
    codes = {(item["code"], item["field"]) for item in profile["issues"]}

    assert profile["rowCount"] == 9
    assert fields["company_id"]["typeHint"] == "identifier"
    assert fields["company_id"]["leadingZeroCount"] == 9
    assert profile["keyCandidates"][0]["duplicateValues"] == 1
    assert fields["amount"]["typeHint"] == "mixed"
    assert fields["amount"]["numericSummary"] is not None
    assert fields["amount"]["numericSummary"]["outlierCount"] == 1
    assert fields["amount"]["topValues"][0]["count"] == 3
    assert fields["category"]["typeHint"] == "category"
    assert ("MIXED_NUMERIC", "amount") in codes
    assert ("MIXED_DATE", "as_of") in codes
    assert ("DUPLICATE_KEY", "company_id") in codes
    assert ("WHITESPACE", "amount") in codes


def test_inspect_csv_detects_imbalanced_candidate_without_assigning_label_meaning() -> None:
    content = "company_id,adverse_status\n" + "".join(
        f"{index:03d},{int(index >= 95)}\n" for index in range(100)
    )

    profile = inspect_csv(content.encode())
    candidate = profile["labelCandidates"][0]
    assert candidate["field"] == "adverse_status"
    assert candidate["minorityShare"] == 0.05
    assert {(value["value"], value["count"]) for value in candidate["values"]} == {
        ("0", 95), ("1", 5),
    }
    assert any(issue["code"] == "POSSIBLE_CLASS_IMBALANCE" for issue in profile["issues"])
