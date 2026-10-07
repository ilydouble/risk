"""sg-comrisk-v1: fixed semantics for the colleague's export, not an AutoML mapper."""

from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from service.adapters.archive import data_root, unpack
from service.files import digest, read_json, write_json

FEATURES = [
    "officers",
    "name_change_count",
    "has_unit",
    "related_company_count",
    "related_company_weighted",
    "address_trust",
]
REQUIRED = {
    "company_attr": ["company_id", *FEATURES],
    "label": ["company_id", "label", "is_labeled"],
    "id_map": ["company_id_str", "company_id_int"],
    "edges": ["src_id", "dst_id", "rel_type", "weight"],
    "splits_5seed": ["seed", "split", "node_idx"],
}


def connect(root: Path) -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(config={"threads": 2, "memory_limit": "1GB"})
    for name, columns in REQUIRED.items():
        path = root / f"{name}.parquet"
        if not path.is_file() or not set(columns).issubset(pq.read_schema(path).names):
            connection.close()
            raise ValueError(f"Missing file or required columns: {name}")
        relation = connection.read_parquet(str(path))
        if name == "id_map":
            relation = relation.project("company_id_str AS company_id, company_id_int AS node_idx")
        relation.create_view(name)
    return connection


def validate(source: Path, destination: Path) -> dict[str, Any]:
    files = unpack(source, destination)
    root = data_root(destination)
    config = read_json(root / "feature_config.json")
    export = read_json(root / "export_meta.json")
    if config.get("protocol_version") != "2.0":
        raise ValueError("Expected feature_config protocol_version 2.0")
    if config["protocols"]["A_no_priors"]["numeric_features"] != FEATURES:
        raise ValueError("A_no_priors feature order is incompatible")
    expected_types = {
        "id_map": {"company_id_str": "string", "company_id_int": "integer"},
        "company_attr": {"company_id": "string"},
        "label": {"company_id": "string", "label": "number", "is_labeled": "mask"},
        "edges": {"src_id": "string", "dst_id": "string", "rel_type": "string", "weight": "number"},
        "splits_5seed": {"seed": "integer", "node_idx": "integer", "split": "string"},
    }
    for name, columns in expected_types.items():
        schema = pq.read_schema(root / f"{name}.parquet")
        for column, kind in columns.items():
            if column not in schema.names:
                raise ValueError(f"Missing column: {name}.{column}")
            dtype = schema.field(column).type
            if pa.types.is_dictionary(dtype):
                dtype = dtype.value_type  # Parquet categoricals retain their scalar value contract.
            checks = {
                "string": pa.types.is_string(dtype) or pa.types.is_large_string(dtype),
                "integer": pa.types.is_integer(dtype),
                "number": pa.types.is_integer(dtype) or pa.types.is_floating(dtype),
                "mask": pa.types.is_integer(dtype) or pa.types.is_boolean(dtype),
            }
            if not checks[kind]:
                raise ValueError(f"Incompatible column type: {name}.{column}")
    with connect(root) as db:

        def require_empty(query: str, message: str) -> None:
            if db.execute(query).fetchone():
                raise ValueError(message)

        for table in ("company_attr", "label", "id_map"):
            require_empty(
                f"SELECT company_id FROM {table} GROUP BY company_id "
                "HAVING count(*) != 1 OR company_id IS NULL LIMIT 1",
                f"Duplicate or null company ID: {table}",
            )
        # Frozen split indices refer to physical company_attr row order.
        require_empty(
            "SELECT 1 FROM (SELECT company_id, row_number() OVER ()-1 AS idx "
            "FROM company_attr) a FULL JOIN id_map m USING(company_id) "
            "WHERE a.idx IS NULL OR m.node_idx IS NULL OR a.idx != m.node_idx LIMIT 1",
            "id_map does not match company_attr row order",
        )
        require_empty(
            "SELECT 1 FROM company_attr a FULL JOIN label l USING(company_id) "
            "WHERE a.company_id IS NULL OR l.company_id IS NULL OR "
            "l.is_labeled IS NULL OR l.is_labeled NOT IN (0,1) OR "
            "(l.is_labeled=1 AND (l.label IS NULL OR l.label NOT IN (0,1))) LIMIT 1",
            "Invalid labels or masks",
        )
        require_empty(
            "SELECT 1 FROM edges e LEFT JOIN id_map s ON e.src_id=s.company_id "
            "LEFT JOIN id_map d ON e.dst_id=d.company_id WHERE s.node_idx IS NULL "
            "OR d.node_idx IS NULL OR e.rel_type IS NULL OR e.rel_type='' "
            "OR e.weight IS NULL OR NOT isfinite(e.weight) OR e.weight<=0 LIMIT 1",
            "Invalid edge endpoint, relation or weight",
        )
        require_empty(
            "SELECT 1 FROM splits_5seed WHERE seed IS NULL OR seed NOT IN (0,1,2,3,4) "
            "OR split IS NULL OR split NOT IN ('train','val','test') LIMIT 1",
            "Invalid frozen split",
        )
        require_empty(
            "SELECT seed,node_idx FROM splits_5seed GROUP BY seed,node_idx "
            "HAVING count(*)!=1 LIMIT 1",
            "Overlapping frozen splits",
        )
        require_empty(
            "SELECT 1 FROM splits_5seed s LEFT JOIN id_map m USING(node_idx) "
            "LEFT JOIN label l USING(company_id) WHERE m.company_id IS NULL "
            "OR l.is_labeled IS DISTINCT FROM 1 LIMIT 1",
            "Split contains unlabeled ID",
        )
        labeled = db.execute("SELECT count(*) FROM label WHERE is_labeled=1").fetchall()[0][0]
        groups = db.execute("SELECT seed,count(*) FROM splits_5seed GROUP BY seed").fetchall()
        if sorted(groups) != [(i, labeled) for i in range(5)]:
            raise ValueError("Each seed must partition all labeled companies")
        for name in FEATURES:
            dtype = pq.read_schema(root / "company_attr.parquet").field(name).type
            if not (
                pa.types.is_integer(dtype)
                or pa.types.is_floating(dtype)
                or pa.types.is_boolean(dtype)
            ):
                raise ValueError(f"Numeric feature has incompatible type: {name}")
        counts = {
            name: db.execute(f"SELECT count(*) FROM {name}").fetchall()[0][0] for name in REQUIRED
        }
        splits = [
            {"seed": r[0], "split": r[1], "count": r[2], "positives": r[3]}
            for r in db.execute(
                "SELECT s.seed,s.split,count(*),sum(l.label)::BIGINT "
                "FROM splits_5seed s JOIN id_map m USING(node_idx) "
                "JOIN label l USING(company_id) GROUP BY s.seed,s.split "
                "ORDER BY s.seed,s.split"
            ).fetchall()
        ]
        positive = db.execute(
            "SELECT count(*) FROM label WHERE is_labeled=1 AND label=1"
        ).fetchall()[0][0]
        relations = [
            {"type": r[0], "count": r[1]}
            for r in db.execute(
                "SELECT rel_type,count(*) FROM edges GROUP BY rel_type ORDER BY rel_type"
            ).fetchall()
        ]
    # Scan every Parquet, including optional attachments, to detect truncated row groups.
    for path in destination.rglob("*.parquet"):
        for _ in pq.ParquetFile(path).iter_batches(batch_size=65536):
            pass
    manifest = {
        "protocol": "sg-comrisk-v1",
        "sha256": digest(source),
        "files": files,
        "counts": counts,
        "labeledCount": labeled,
        "positiveCount": positive,
        "splits": splits,
        "relations": relations,
        "features": FEATURES,
        "source": export,
        "limitations": [
            "Singapore corporate distress proxy",
            "Static graph",
            "Training uses smoke-v1 subset; no credit-default claim",
        ],
    }
    write_json(destination / "validation.json", manifest)
    return manifest


def verify_validated(directory: Path) -> dict[str, Any]:
    """Cached Parquet must still match the server-produced validation manifest."""
    manifest = read_json(directory / "validation.json")
    if manifest.get("protocol") != "sg-comrisk-v1":
        raise ValueError("Unsupported validated dataset protocol")
    for item in manifest["files"]:
        path = directory / item["path"]
        if not path.resolve().is_relative_to(directory.resolve()) or path.is_symlink():
            raise ValueError("Invalid dataset manifest path")
        if not path.is_file() or path.stat().st_size != item["size"]:
            raise ValueError("Validated dataset file is missing or changed")
        if digest(path) != item["sha256"]:
            raise ValueError("Validated dataset checksum mismatch")
    return manifest
