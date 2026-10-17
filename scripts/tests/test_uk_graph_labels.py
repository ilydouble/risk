"""Adverse supervision never becomes graph attributes or relationships."""

import sys
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from isolate_uk_graph_labels import (
    clean_node,
    graph_identity,
    rewrite_graphml,
)


def test_event_metadata_is_removed_and_event_name_uses_independent_evidence():
    original = {
        "id": "00000001",
        "kind": "company",
        "name": "Event name",
        "name_source": "event_record_reference",
        "name_source_date": "2025-01",
        "name_missing": "False",
        "event_reference_sic2007": "12345",
        "snapshot_sic2007": "67890",
    }
    node = clean_node(original, {"00000001": "Historic <Company>"})
    assert node["name"] == "Historic <Company>"
    assert node["name_source"] == "selected_historical_report"
    assert node["snapshot_sic2007"] == "67890"
    assert "event_reference_sic2007" not in node
    assert original["name"] == "Event name"
    fallback = clean_node(original, {})
    assert fallback["name"] == "00000001"
    assert fallback["name_missing"] == "True"


def test_unrelated_registry_name_and_fields_are_preserved():
    row = {
        "id": "1",
        "name": "Registry name",
        "name_source": "companies_house_snapshot",
    }
    assert clean_node(row, {"1": "Other name"}) == row


def test_all_graphml_event_fields_removed_without_mutating_topology(tmp_path):
    source, target = tmp_path / "old.graphml", tmp_path / "new.graphml"
    source.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
<key id="event_reference_sic2007" for="node" attr.name="event_reference_sic2007"/>
<key id="name" for="node" attr.name="name" attr.type="string"/>
<graph id="g" edgedefault="directed">
<node id="1"><data key="name">E</data><data key="event_reference_sic2007">12345</data></node>
<node id="GROUP:1"><data key="name">Group</data><data key="event_reference_sic2007"></data></node>
<edge id="m" source="1" target="GROUP:1"><data key="edge_relation">MEMBER</data></edge>
</graph></graphml>
""")
    rewrite_graphml(source, target, {"1": {"name": "A & B <Ltd>"}})
    assert graph_identity(source) == graph_identity(target)
    ns = {"g": "http://graphml.graphdrawing.org/xmlns"}
    root = ET.parse(target).getroot()
    assert root.find(".//g:node/g:data[@key='name']", ns).text == "A & B <Ltd>"
    assert "event_reference" not in target.read_text()
