from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pandas as pd

from workbench.sg_overview import build_singapore_overview


def _parquet(frame: pd.DataFrame) -> bytes:
    stream = io.BytesIO()
    frame.to_parquet(stream, index=False)
    return stream.getvalue()


def _archive(path: Path) -> Path:
    companies = pd.DataFrame(
        {
            "company_id": ["A", "B", "C", "D"],
            "name": ["Alpha", "Beta", "Gamma", "Delta"],
            "age_years": [2.0, 8.0, 15.0, 55.0],
            "ssic_code": ["01", "02", "03", "04"],
            "ssic2": ["01", "02", "03", "04"],
            "setup_time_months": [24.0, 96.0, 180.0, 660.0],
            "country": ["SG"] * 4,
            "officers": [1.0, 2.0, 3.0, 4.0],
            "name_change_count": [0, 1, 0, 2],
            "has_unit": [1, 0, 1, 1],
            "register_capital": [None] * 4,
            "paid_capital": [None] * 4,
        }
    )
    labels = pd.DataFrame(
        {
            "company_id": ["A", "B", "C", "D"],
            "label": [0.0, 1.0, None, 0.0],
            "is_labeled": [1, 1, 0, 1],
            "status_detail": ["Live", "Liquidation", "Struck Off", "Live"],
        }
    )
    edges = pd.DataFrame(
        {
            "src_id": ["A", "B"],
            "dst_id": ["B", "C"],
            "rel_type": ["SAME_ADDRESS", "EQUITY_DIRECT"],
            "weight": [0.5, 0.8],
        }
    )
    group = pd.DataFrame({"company_id": ["A", "B", "C", "D"], "group_value": ["x", "x", "y", "z"]})
    risk = pd.DataFrame(
        columns=["company_id", "case_id", "case_type", "court_level", "outcome", "date"]
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "comrisk_export/export_meta.json",
            json.dumps(
                {
                    "generated_at": "2026-09-25T20:21:21",
                    "scope": "Singapore only",
                }
            ),
        )
        archive.writestr("comrisk_export/company_attr.parquet", _parquet(companies))
        archive.writestr("comrisk_export/label.parquet", _parquet(labels))
        archive.writestr("comrisk_export/edges.parquet", _parquet(edges))
        archive.writestr("comrisk_export/risk_data.parquet", _parquet(risk))
        for name in ("industry", "area", "qualify"):
            archive.writestr(f"comrisk_export/hypergraph_{name}.parquet", _parquet(group))
    return path


def test_build_singapore_overview_uses_real_aggregate_semantics(tmp_path: Path) -> None:
    source = _archive(tmp_path / "comrisk.zip")

    snapshot = build_singapore_overview(source)

    assert (
        snapshot["dataset"]["sourceArchiveSha256"]
        == hashlib.sha256(source.read_bytes()).hexdigest()
    )
    assert snapshot["stats"] == {
        "companyCount": 4,
        "labeledCount": 3,
        "distressCount": 1,
        "healthyCount": 2,
        "unlabeledCount": 1,
        "edgeCount": 2,
    }
    assert snapshot["labelDistribution"] == [
        {"key": "healthy", "value": 2},
        {"key": "distress", "value": 1},
        {"key": "unlabeled", "value": 1},
    ]
    assert snapshot["quality"]["ordinaryEdgeCoverageWithinLabeled"] == 2 / 3
    assert snapshot["quality"]["capitalCoverage"] == 0
    assert snapshot["quality"]["litigationRows"] == 0
    assert snapshot["sampling"] == {
        "strategy": "deterministic_stratified_hash",
        "requestedPerClass": 100,
        "sampleCount": 4,
        "representative": False,
    }
    assert {item["companyId"] for item in snapshot["sampleCompanies"]} == {
        "A",
        "B",
        "C",
        "D",
    }
    companies = {item["companyId"]: item for item in snapshot["sampleCompanies"]}
    assert companies["B"]["facts"] == {
        "country": "SG",
        "setupTimeMonths": 96.0,
        "industryDivisionCode": "02",
        "officerCount": 2,
        "nameChangeCount": 1,
        "hasUnit": False,
        "registeredCapital": None,
        "paidCapital": None,
    }
    assert companies["B"]["relationProfile"]["byType"] == [
        {"type": "EQUITY_DIRECT", "count": 1},
        {"type": "SAME_ADDRESS", "count": 1},
    ]
    assert [item["companyId"] for item in companies["B"]["relationProfile"]["neighbors"]] == [
        "C",
        "A",
    ]
    assert companies["B"]["groups"] == [
        {"type": "industry", "value": "x", "memberCount": 2},
        {"type": "area", "value": "x", "memberCount": 2},
        {"type": "qualify", "value": "x", "memberCount": 2},
    ]
    assert companies["D"]["dataAvailability"]["relations"] == "no_records"
