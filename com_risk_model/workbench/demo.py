from __future__ import annotations

import csv
import hashlib
import io
import json
import random
import zipfile
from pathlib import Path
from typing import Literal


def _csv_bytes(rows: list[dict[str, object]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def build_demo_bundle(
    output: str | Path,
    task_type: Literal["loan_application", "entity_snapshot"] = "loan_application",
    *,
    rows: int = 180,
    seed: int = 42,
) -> Path:
    """Create a deterministic Bundle v1 used by local acceptance tests and demos."""
    if rows < 60:
        raise ValueError("demo bundle requires at least 60 samples")
    rng = random.Random(seed)
    samples: list[dict[str, object]] = []
    for index in range(rows):
        split = "train" if index < rows * 0.6 else "validation" if index < rows * 0.8 else "test"
        debt_ratio = round(rng.uniform(0.05, 0.95), 5)
        overdue_count = rng.randrange(0, 5)
        years = rng.randrange(1, 25)
        probability = 0.08 + 0.5 * debt_ratio + 0.08 * overdue_count - 0.015 * years
        target = int(rng.random() < max(0.02, min(0.9, probability)))
        samples.append(
            {
                "sample_id": f"S{index:05d}",
                "entity_id": f"C{index % 72:04d}",
                "observation_time": f"2025-{index % 12 + 1:02d}-01T00:00:00Z",
                "graph_snapshot_id": f"G{index % 3}",
                "split": split,
                "target": target,
                "debt_ratio": debt_ratio,
                "overdue_count": overdue_count,
                "company_age_years": years,
                "industry": f"I{index % 5}",
            }
        )
    samples_bytes = _csv_bytes(samples)
    target_name = "default_12m" if task_type == "loan_application" else "business_distress_12m"
    target_definition = (
        "申请后 12 个月内发生约定口径的逾期或违约"
        if task_type == "loan_application"
        else "观察时点后 12 个月内发生约定口径的经营异常"
    )
    metadata = {
        "schemaVersion": 1,
        "datasetName": f"synthetic-{task_type}",
        "taskType": task_type,
        "sampleUnit": task_type,
        "columns": {
            "sampleId": "sample_id",
            "entityId": "entity_id",
            "observationTime": "observation_time",
            "graphSnapshotId": "graph_snapshot_id",
            "split": "split",
            "target": "target",
        },
        "target": {
            "name": target_name,
            "positiveValue": 1,
            "predictionWindowDays": 365,
            "businessDefinition": target_definition,
        },
        "features": [
            {"name": "debt_ratio", "kind": "numeric", "group": "financial"},
            {"name": "overdue_count", "kind": "numeric", "group": "bureau"},
            {"name": "company_age_years", "kind": "numeric", "group": "registry"},
            {"name": "industry", "kind": "categorical", "group": "registry"},
        ],
        "files": {
            "samples": {
                "path": "samples.csv",
                "format": "csv",
                "sizeBytes": len(samples_bytes),
                "sha256": hashlib.sha256(samples_bytes).hexdigest(),
            }
        },
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2))
        archive.writestr("samples.csv", samples_bytes)
    return output
