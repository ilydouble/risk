"""Use the existing workbench protocols for three standard package profiles."""

import shutil
from collections.abc import Iterable
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import duckdb

from riskgnn.dataset_adapters.archive import unpack
from riskgnn.dataset_adapters.base import DatasetAdapter
from riskgnn.dataset_adapters.contract import CONTRACT_NAME
from riskgnn.dataset_adapters.contracts.enterprise import EnterpriseRecord
from riskgnn.dataset_adapters.contracts.inspection import InspectionResult
from riskgnn.dataset_adapters.snapshot_io import SPLITS
from riskgnn.dataset_adapters.standard.contract import check_resources
from riskgnn.dataset_adapters.standard.snapshots import restore_smesd, restore_uk
from riskgnn.workbench.artifacts import digest, write_json


def restore_acra(source: Path, native: Path) -> None:
    with duckdb.connect(config={"threads": 2, "memory_limit": "1GB"}) as db:
        for name in (
            "entities",
            "observations",
            "labels",
            "edges",
            "splits",
            "groups",
            "memberships",
        ):
            db.read_parquet(str(source / f"{name}.parquet")).create_view(name)
        db_query = {
            "id_map": (
                "SELECT entity_id AS company_id_str, source_index AS company_id_int "
                "FROM entities ORDER BY source_index"
            ),
            "company_attr": (
                "SELECT o.* EXCLUDE(sample_id) FROM observations o "
                "JOIN entities e ON o.company_id=e.entity_id ORDER BY e.source_index"
            ),
            "label": "SELECT sample_id AS company_id, * EXCLUDE(sample_id) FROM labels",
            "edges": (
                "SELECT edge_id AS relation_id, source AS src_id, target AS dst_id, "
                "relation AS rel_type, * EXCLUDE(edge_id,source,target,relation) FROM edges"
            ),
            "splits_5seed": ("SELECT seed,split,node_idx FROM splits ORDER BY source_position"),
            "hyperedge_groups": "SELECT group_id AS group_value, * EXCLUDE(group_id) FROM groups",
        }
        for kind in ("area", "industry", "qualify"):
            db_query[f"hypergraph_{kind}"] = (
                "SELECT sample_id AS company_id,group_id AS group_value,kind AS group_type,"
                f"membership_confidence FROM memberships WHERE kind='{kind}' "
                "ORDER BY source_position"
            )
        for name, query in db_query.items():
            db.sql(query).write_parquet(str(native / f"{name}.parquet"), compression="zstd")
    for name in ("feature_config.json", "export_meta.json"):
        shutil.copy2(source / name, native / name)


class NativePackageAdapter(DatasetAdapter):
    def __init__(self, adapter: DatasetAdapter, contract: dict, descriptor: dict):
        self.adapter = adapter
        self.id, self.version, self.trainable = adapter.id, adapter.version, adapter.trainable
        self.contract, self.descriptor = contract, descriptor

    def inspect(self, archive: Path, workspace: Path, config: dict) -> InspectionResult:
        package = workspace / "package"
        files = unpack(archive, package)
        check_resources(self.descriptor, files)
        with TemporaryDirectory(dir=workspace) as temporary:
            scratch = Path(temporary)
            native = scratch / "files"
            native.mkdir()
            self.restore(package, native)
            write_json(native / CONTRACT_NAME, self.contract)
            projected = scratch / "native.zip"
            with ZipFile(projected, "w") as zip_file:
                for path in sorted(native.iterdir()):
                    zip_file.write(path, path.name)
            result = self.adapter.inspect(projected, workspace / "native", config)
        summary = result.model_dump(mode="python", exclude_unset=True)
        summary["sha256"] = digest(archive)
        summary["files"] = [
            {**entry, "path": f"{prefix}/{entry['path']}"}
            for prefix, entries in (("package", files), ("native", summary["files"]))
            for entry in entries
        ]
        summary["root"] = "native"
        summary["metadata"] = {**summary.get("metadata", {}), "inputFormat": "data-package-2.0"}
        return InspectionResult.model_validate(summary)

    def restore(self, package: Path, native: Path) -> None:
        if self.id == "sg-comrisk":
            restore_acra(package, native)
            return
        restore = restore_uk if self.id == "uk-dataset-v1" else restore_smesd
        for split in SPLITS:
            restore(package, native / f"{split}.json", split)
        names = ("audit.json",)
        if self.id == "uk-dataset-v1":
            names += ("export_meta.json", "feature-policy.json", "split-audit.csv")
        for name in names:
            shutil.copy2(package / name, native / name)

    def prepare(self, validated: Path, output: Path, config: dict) -> dict:
        return self.adapter.prepare(validated, output, config)

    def enterprise_records(self, validated: Path) -> Iterable[EnterpriseRecord]:
        return self.adapter.enterprise_records(validated)
