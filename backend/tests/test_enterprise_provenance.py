from copy import deepcopy

import pytest

from risk_api.modules.data_prep.conversion import ConversionPlan, execute
from risk_api.modules.data_prep.lineage import trace_company
from risk_api.modules.modeling.api.schemas import ResponseEnterpriseProvenance

RULES = {
    "deduplicate": "exact",
    "labelMeaning": "snapshot status",
    "columns": [
        {"field": "id", "target": "enterprise.id", "type": "text"},
        {"field": "value", "target": "features.value", "type": "number", "missing": "null"},
        {
            "field": "status",
            "target": "enterprise.label",
            "type": "label",
            "values": {"0": 0, "1": 1},
        },
        {"field": "note", "target": "", "type": "ignore"},
    ],
}
SOURCE = b'id,value,status,note\r\n001,,0,"hello\nworld"\r\n002,0,1,x\r\n001,,0,"hello\nworld"\r\n'


def test_trace_original_values_ignored_fields_and_physical_multiline_locations():
    plan = ConversionPlan.model_validate(RULES)
    records, report = execute(SOURCE, plan)
    assert report["passed"]
    lineage = trace_company(SOURCE, plan, "001", records[0]["data"])
    assert lineage["sourceRow"] == 1
    assert lineage["sourceLine"] == 2 and lineage["sourceEndLine"] == 3
    assert lineage["duplicateLines"] == [5] and lineage["duplicateCount"] == 1
    fields = {field["rule"]["field"]: field for field in lineage["fields"]}
    assert fields["id"]["originalValue"] == fields["id"]["convertedValue"] == "001"
    assert fields["value"]["originalValue"] == "" and fields["value"]["convertedValue"] is None
    assert fields["note"]["ignored"] and fields["note"]["originalValue"] == "hello\nworld"
    assert fields["note"]["convertedValue"] is None
    second = trace_company(SOURCE, plan, "002", records[1]["data"])
    assert second["sourceRow"] == 2 and second["sourceLine"] == 4
    assert next(f for f in second["fields"] if f["rule"]["field"] == "value")["convertedValue"] == 0
    ResponseEnterpriseProvenance.model_validate(
        {"status": "available", "message": "verified", **lineage}
    )


def test_trace_rejects_ambiguous_identity_or_changed_record():
    plan = ConversionPlan.model_validate(RULES)
    record = execute(SOURCE, plan)[0][0]
    changed = deepcopy(record["data"])
    changed["features"]["value"] = 999
    with pytest.raises(ValueError, match="differs"):
        trace_company(SOURCE, plan, "001", changed)
    source = SOURCE + b"001,999,0,changed\n"
    with pytest.raises(ValueError, match="ambiguous"):
        trace_company(source, plan, "001", record["data"])
    with pytest.raises(ValueError, match="unavailable"):
        trace_company(SOURCE, plan, "missing", record["data"])


def test_trace_caps_display_only_and_keeps_duplicate_count():
    plan = ConversionPlan.model_validate(RULES)
    row = "001,0,0," + "a" * 5000 + "\n"
    source = ("id,value,status,note\n" + row * 105).encode()
    record = execute(source, plan)[0][0]
    lineage = trace_company(source, plan, "001", record["data"])
    assert lineage["duplicateCount"] == 104 and len(lineage["duplicateLines"]) == 100
    assert lineage["duplicatesTruncated"]
    field = next(f for f in lineage["fields"] if f["rule"]["field"] == "note")
    assert field["originalTruncated"] and len(field["originalValue"]) == 4096
    assert row.count("a") == 5000


def test_trace_counts_physical_blank_lines_without_treating_them_as_records():
    source = b"id,value,status,note\n\n001,0,0,x\n\n001,0,0,x\n"
    plan = ConversionPlan.model_validate(RULES)
    record = execute(source, plan)[0][0]
    lineage = trace_company(source, plan, "001", record["data"])
    assert lineage["sourceRow"] == 1 and lineage["sourceLine"] == 3
    assert lineage["duplicateLines"] == [5]
