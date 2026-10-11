import hashlib
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from riskgnn.dataset_adapters.analysis.bundle import analyze_bundle
from riskgnn.dataset_adapters.analysis.report import normalize
from riskgnn.dataset_adapters.base import DatasetAdapter
from riskgnn.dataset_adapters.bundle.data import load_bundle
from riskgnn.workbench.artifacts import digest


def inspect_bundle(source: Path, destination: Path) -> dict:
    with ZipFile(source) as archive:
        names = set(archive.namelist())
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
    return result


class BundleAdapter(DatasetAdapter):
    id = "bundle"
    version = "1"
    trainable = False

    def inspect(self, archive: Path, workspace: Path, config: dict) -> dict:
        if config:
            raise ValueError("bundle v1 does not accept additional configuration")
        return inspect_bundle(archive, workspace)

    def prepare(self, validated: Path, output: Path, config: dict) -> dict:
        raise ValueError("Bundle is analysis-only for the current RiskGNN model")
