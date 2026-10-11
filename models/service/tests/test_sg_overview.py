import pandas as pd

from riskgnn.dataset_adapters.acra.overview import build_singapore_overview
from riskgnn.dataset_adapters.acra.validation import validate


def test_overview_preserves_existing_page_fields_from_validated_real_data(export_zip, tmp_path):
    manifest = validate(export_zip, tmp_path / "validated")
    result = build_singapore_overview(tmp_path / "validated")
    labels = pd.read_parquet(tmp_path / "source/label.parquet")
    assert result["stats"]["companyCount"] == len(labels)
    assert result["stats"]["labeledCount"] == int(labels.is_labeled.sum())
    assert result["stats"]["distressCount"] == int((labels.label == 1).sum())
    assert result["stats"]["edgeCount"] == manifest["counts"]["edges"]
    assert result["quality"]["capitalCoverage"] == 0
    assert result["quality"]["litigationRows"] == 0
    assert result["dataset"]["sourceArchiveSha256"] == manifest["sha256"]
    assert result["sampling"]["representative"] is False
    assert result["sampleCompanies"]
    for company in result["sampleCompanies"]:
        assert {"facts", "relationProfile", "groups", "dataAvailability"} <= company.keys()
