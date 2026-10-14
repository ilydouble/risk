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


def test_inspect_csv_rejects_extra_cells() -> None:
    with pytest.raises(AppError) as caught:
        inspect_csv(b"id,label\n1,0,extra\n")

    assert caught.value.code == "DATA_PREP_ROW_INVALID"


def test_inspect_csv_rejects_duplicate_headers() -> None:
    with pytest.raises(AppError) as caught:
        inspect_csv(b"id,id\n1,2\n")

    assert caught.value.code == "DATA_PREP_HEADER_DUPLICATE"
