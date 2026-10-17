"""Readable, pre-transform data shared by model preparation and enterprise browsing."""

import json
import math
from collections.abc import Iterable
from pathlib import Path
from tempfile import NamedTemporaryFile

from riskgnn.dataset_adapters.base import DatasetAdapter
from riskgnn.dataset_adapters.contracts.enterprise import (
    MAX_BYTES,
    MAX_LINE,
    EnterpriseExportSummary,
    EnterpriseManifest,
    EnterpriseRecord,
)
from riskgnn.dataset_adapters.contracts.inspection import ValidatedDataset


def attributes(names: list[str], values: Iterable) -> dict:
    return {
        name: None if value is None or not math.isfinite(float(value)) else float(value)
        for name, value in zip(names, values, strict=True)
    }


def feature_vector(values: dict, names: list[str]) -> list:
    return [values[name] for name in names]


def snapshot_records(snapshots: dict) -> Iterable[EnterpriseRecord]:
    for split, snapshot in snapshots.items():
        for node in snapshot.nodes:
            yield EnterpriseRecord.model_validate({
                "kind": node.kind,
                "snapshot": split,
                "nodeId": node.id,
                "data": {
                    "name": node.name,
                    "properties": node.properties,
                    "attributes": attributes(snapshot.feature_names, node.features),
                    "community": node.community,
                    "label": node.label,
                    "split": node.split,
                },
            })
        for edge in snapshot.edges:
            yield EnterpriseRecord.model_validate({
                "kind": "edge",
                "snapshot": split,
                "source": edge.source,
                "target": edge.target,
                "data": edge.model_dump(exclude_none=True),
            })
        for group in snapshot.hyperedges:
            yield EnterpriseRecord.model_validate({
                "kind": "hyperedge",
                "snapshot": split,
                "members": group.members,
                "data": group.model_dump(exclude_none=True),
            })
        for event in snapshot.events:
            yield EnterpriseRecord.model_validate({
                "kind": "event",
                "snapshot": split,
                "source": event.company,
                "data": event.model_dump(exclude_none=True),
            })


def export(
    adapter: DatasetAdapter, validated: Path, output: Path, inspection: dict,
) -> EnterpriseExportSummary:
    inspection_data = ValidatedDataset.model_validate(inspection)
    header = EnterpriseManifest(
        datasetContract=inspection_data.datasetContract,
        sourceSha256=inspection_data.sha256,
        featureNames=inspection_data.features,
        target=inspection_data.datasetProfile.target,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    counts: dict = {}
    size = 0
    temporary: Path | None = None
    try:
        # Publish only a fully checked file, never a partially exported artifact.
        with NamedTemporaryFile(
            mode="wb", dir=output.parent, suffix=".jsonl", delete=False,
        ) as stream:
            temporary = Path(stream.name)

            def write(value: dict) -> None:
                nonlocal size
                line = (json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n").encode()
                size += len(line)
                if len(line) > MAX_LINE or size > MAX_BYTES:
                    raise ValueError("Enterprise export exceeds the import size limit")
                stream.write(line)

            write(header.model_dump(mode="json"))
            for number, candidate in enumerate(adapter.enterprise_records(validated), start=1):
                if not isinstance(candidate, EnterpriseRecord):
                    raise TypeError("Adapter.enterprise_records must yield EnterpriseRecord")
                # Revalidate constructed/mutated instances before crossing the CLI boundary.
                try:
                    record = EnterpriseRecord.model_validate(candidate.model_dump(mode="python"))
                    if record.kind == "company":
                        attrs = record.data["attributes"]
                        if not isinstance(attrs, dict) or not set(
                            inspection_data.features
                        ).issubset(attrs):
                            raise ValueError("Company attributes must include declared features")
                    counts[record.kind] = counts.get(record.kind, 0) + 1
                    write(record.model_dump(mode="json", exclude_none=True))
                except ValueError as error:
                    raise ValueError(f"Invalid enterprise record #{number}: {error}") from error
            for source_kind, exported_kind in {
                "company_attr": "company", "persons": "person", "edges": "edge",
                "hyperedges": "hyperedge", "events": "event",
            }.items():
                if source_kind in inspection_data.counts and counts.get(exported_kind, 0) != (
                    inspection_data.counts[source_kind]
                ):
                    raise ValueError(f"Exported {exported_kind} count does not match inspection")
            summary = EnterpriseExportSummary(counts=counts)
        temporary.replace(output)
        return summary
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
