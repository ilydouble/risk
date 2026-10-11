"""Read the shared snapshot container without executing its attachments."""

from collections.abc import Callable
from pathlib import Path

from riskgnn.dataset_adapters.archive import unpack
from riskgnn.dataset_adapters.contract import read_contract
from riskgnn.dataset_adapters.snapshot_schema import Snapshot
from riskgnn.workbench.artifacts import digest, read_json, write_json

SPLITS = ("train", "valid", "test")


def load(root: Path) -> dict[str, Snapshot]:
    return {
        split: Snapshot.model_validate_json((root / f"{split}.json").read_bytes())
        for split in SPLITS
    }


def validate(
    source: Path, destination: Path, protocol: str, check: Callable[[dict[str, Snapshot]], None]
) -> dict:
    contract, relative = read_contract(source)
    files = unpack(source, destination)
    root = destination / relative
    snapshots = load(root)
    seen: set[str] = set()
    reference = snapshots["train"]
    for split, snapshot in snapshots.items():
        if any(
            getattr(snapshot, key) != getattr(reference, key)
            for key in ("feature_names", "relation_names", "hyperedge_types", "target_description")
        ):
            raise ValueError("Snapshot schemas or target definitions disagree")
        companies = [n for n in snapshot.nodes if n.kind == "company"]
        ids = {n.id for n in companies}
        if ids & seen:
            raise ValueError("Overlapping company splits")
        seen.update(ids)
        if any(n.split != split or n.label is None for n in companies):
            raise ValueError("Company label/split does not match snapshot")
        if {n.label for n in companies} != {0, 1}:
            raise ValueError("Each snapshot must contain both labels")
    check(snapshots)
    result = {
        "protocol": protocol,
        "datasetContract": contract,
        "root": relative,
        "sha256": digest(source),
        "files": files,
        "counts": {
            "company_attr": len(seen),
            "persons": sum(n.kind == "person" for d in snapshots.values() for n in d.nodes),
            "edges": sum(len(d.edges) for d in snapshots.values()),
            "hyperedges": sum(len(d.hyperedges) for d in snapshots.values()),
            "events": sum(len(d.events) for d in snapshots.values()),
        },
        "labeledCount": len(seen),
        "positiveCount": sum(n.label == 1 for d in snapshots.values() for n in d.nodes),
        "features": reference.feature_names,
        "splits": [
            {
                "split": split,
                "count": sum(n.kind == "company" for n in d.nodes),
                "positives": sum(n.label == 1 for n in d.nodes),
            }
            for split, d in snapshots.items()
        ],
        "datasetProfile": {
            "datasetFormat": protocol,
            "taskType": "entity_snapshot",
            "target": reference.target_description,
            "evaluation": reference.evaluation,
        },
    }
    write_json(destination / "validation.json", result)
    return result


def verified(directory: Path, protocol: str) -> tuple[dict, Path]:
    manifest = read_json(directory / "validation.json")
    if manifest["protocol"] != protocol:
        raise ValueError("Validated dataset protocol mismatch")
    for entry in manifest["files"]:
        path = directory / entry["path"]
        if not path.resolve().is_relative_to(directory.resolve()) or path.is_symlink():
            raise ValueError("Invalid dataset manifest path")
        if (
            not path.is_file()
            or path.stat().st_size != entry["size"]
            or digest(path) != entry["sha256"]
        ):
            raise ValueError("Validated dataset changed")
    root = directory / manifest["root"]
    if not root.resolve().is_relative_to(directory.resolve()):
        raise ValueError("Invalid dataset root")
    return manifest, root
