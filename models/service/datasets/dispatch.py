import hashlib
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from service.adapters.archive import data_root
from service.adapters.singapore import validate as validate_singapore
from service.analysis.bundle import analyze_bundle
from service.analysis.report import normalize
from service.analysis.singapore import analyze as analyze_singapore
from service.datasets.bundle.data import load_bundle
from service.files import digest, write_json
from service.runners.registry import supported_models


def validate(source: Path, destination: Path) -> dict:
    # Inspect names only; each selected validator enforces its own archive/schema limits.
    with ZipFile(source) as archive:
        names = set(archive.namelist())
    if "metadata.json" in names:
        data = load_bundle(source)
        metadata = data.metadata
        raw = analyze_bundle(data)
        destination.mkdir(parents=True, exist_ok=True)
        result: dict[str, Any] = {
            "protocol": "bundle-v1",
            "sha256": digest(source),
            "files": [],
            "counts": {
                name: len(frame)
                for name in ("samples", "nodes", "relations", "events", "hyperedges")
                if (frame := getattr(data, name)) is not None
            },
            "labeledCount": len(data.samples),
            "positiveCount": int(
                (data.samples.target.astype(str) == str(metadata.target.positive_value)).sum()
            ),
            "analysis": normalize(raw, total_rows=len(data.samples)),
            "datasetProfile": metadata.model_dump(mode="json", by_alias=True),
            "limitations": ["Bundle analysis only; no compatible training runner is registered"],
        }
        with ZipFile(source) as archive:
            for name in sorted(names):
                info = archive.getinfo(name)
                if not info.is_dir():
                    with archive.open(name) as stream:
                        hasher = hashlib.sha256()
                        while chunk := stream.read(1024 * 1024):
                            hasher.update(chunk)
                        sha = hasher.hexdigest()
                    result["files"].append({"path": name, "size": info.file_size, "sha256": sha})
    else:
        result = validate_singapore(source, destination)
        result["analysis"] = analyze_singapore(data_root(destination), result)
        result["datasetProfile"] = {
            "datasetFormat": "sg-comrisk-v1",
            "taskType": "entity_snapshot",
            "target": "Singapore corporate distress proxy",
            "features": result["features"],
            "splits": result["splits"],
            "relations": result["relations"],
        }
    result["supportedRunnerIds"] = supported_models(result["protocol"])
    write_json(destination / "validation.json", result)
    return result
