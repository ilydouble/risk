from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from workbench.bundle import ValidatedBundle, validate_bundle
from workbench.schema import BundleMetadata, FileSpec

CORE_COLUMNS = {
    "sample_id",
    "entity_id",
    "observation_time",
    "graph_snapshot_id",
    "split",
    "target",
}


class DataValidationError(ValueError):
    pass


@dataclass(frozen=True)
class DataLimits:
    max_sample_rows: int = 2_000_000
    max_columns: int = 1000
    max_node_rows: int = 2_000_000
    max_relation_rows: int = 5_000_000
    max_event_rows: int = 5_000_000
    max_hyperedge_rows: int = 5_000_000
    max_gnn_nodes: int = 200_000
    max_gnn_relations: int = 1_000_000


DEFAULT_DATA_LIMITS = DataLimits()


@dataclass
class BundleData:
    metadata: BundleMetadata
    samples: pd.DataFrame
    nodes: pd.DataFrame | None = None
    relations: pd.DataFrame | None = None
    events: pd.DataFrame | None = None
    hyperedges: pd.DataFrame | None = None
    validation: dict[str, object] = field(default_factory=dict)
    capabilities: dict[str, object] = field(default_factory=dict)


def _read_table(archive: zipfile.ZipFile, spec: FileSpec) -> pd.DataFrame:
    payload = archive.read(spec.path)
    try:
        if spec.format == "csv":
            return pd.read_csv(io.BytesIO(payload), low_memory=False)
        return pd.read_parquet(io.BytesIO(payload))
    except Exception as error:
        raise DataValidationError(f"cannot read {spec.path}: {error}") from error


def _require_columns(frame: pd.DataFrame, required: set[str], name: str) -> None:
    missing = required.difference(frame.columns)
    if missing:
        raise DataValidationError(f"{name} is missing columns: {sorted(missing)}")


def _validate_samples(data: BundleData, limits: DataLimits) -> None:
    frame = data.samples
    feature_names = {feature.name for feature in data.metadata.features}
    _require_columns(frame, CORE_COLUMNS | feature_names, "samples")
    if len(frame) == 0 or len(frame) > limits.max_sample_rows:
        raise DataValidationError("sample row count is outside the allowed range")
    if len(frame.columns) > limits.max_columns:
        raise DataValidationError("sample column count exceeds the limit")
    if frame["sample_id"].isna().any() or frame["sample_id"].astype(str).duplicated().any():
        raise DataValidationError("sample_id must be non-empty and unique")
    if frame["entity_id"].isna().any():
        raise DataValidationError("entity_id must be non-empty")
    allowed_splits = {"train", "validation", "test"}
    splits = set(frame["split"].dropna().astype(str))
    if splits != allowed_splits:
        raise DataValidationError("split must contain only train, validation and test")
    parsed_time = pd.to_datetime(frame["observation_time"], errors="coerce", utc=True)
    if parsed_time.isna().any():
        raise DataValidationError("observation_time must be a valid timestamp")
    frame["observation_time"] = parsed_time
    values = set(frame["target"].dropna().astype(str))
    positive = str(data.metadata.target.positive_value)
    if positive not in values or len(values) != 2 or frame["target"].isna().any():
        raise DataValidationError("target must be a complete binary field containing positiveValue")
    train = frame[frame["split"] == "train"]
    if train["target"].astype(str).value_counts().min() < 2:
        raise DataValidationError("each target class needs at least two training samples")


def _validate_graph(data: BundleData, limits: DataLimits) -> None:
    if all(table is None for table in (data.nodes, data.relations, data.events, data.hyperedges)):
        return
    if data.nodes is None:
        raise DataValidationError("nodes is required when graph components are present")
    nodes = data.nodes
    _require_columns(nodes, {"graph_snapshot_id", "node_id", "node_type"}, "nodes")
    if len(nodes) > limits.max_node_rows:
        raise DataValidationError("node row count exceeds the limit")
    keys = nodes[["graph_snapshot_id", "node_id"]].astype(str)
    if keys.duplicated().any() or keys.isna().any().any():
        raise DataValidationError("node keys must be non-empty and unique within snapshots")
    node_keys = set(keys.itertuples(index=False, name=None))
    sample_keys = set(
        data.samples[["graph_snapshot_id", "entity_id"]]
        .astype(str)
        .itertuples(index=False, name=None)
    )
    if sample_keys.difference(node_keys):
        raise DataValidationError("sample entities must exist in their graph snapshot")
    if data.relations is not None:
        relations = data.relations
        _require_columns(
            relations,
            {"graph_snapshot_id", "source_id", "target_id", "relation_type", "weight"},
            "relations",
        )
        if len(relations) > limits.max_relation_rows:
            raise DataValidationError("relation row count exceeds the limit")
        snapshot = relations["graph_snapshot_id"].astype(str)
        sources = set(zip(snapshot, relations["source_id"].astype(str), strict=True))
        targets = set(zip(snapshot, relations["target_id"].astype(str), strict=True))
        if sources.difference(node_keys) or targets.difference(node_keys):
            raise DataValidationError("relations must reference nodes in the same snapshot")
        weights = pd.to_numeric(relations["weight"], errors="coerce")
        if weights.isna().any() or (weights <= 0).any():
            raise DataValidationError("relation weights must be positive numbers")
        relations["weight"] = weights
    if data.events is not None:
        events = data.events
        _require_columns(
            events,
            {"graph_snapshot_id", "node_id", "event_type", "event_time"},
            "events",
        )
        if len(events) > limits.max_event_rows:
            raise DataValidationError("event row count exceeds the limit")
        event_keys = set(
            events[["graph_snapshot_id", "node_id"]]
            .astype(str)
            .itertuples(index=False, name=None)
        )
        if event_keys.difference(node_keys):
            raise DataValidationError("events must reference nodes in the same snapshot")
        times = pd.to_datetime(events["event_time"], errors="coerce", utc=True)
        if times.isna().any():
            raise DataValidationError("event_time must be a valid timestamp")
        events["event_time"] = times
        cutoff = data.samples.groupby("graph_snapshot_id")["observation_time"].min()
        allowed = events["graph_snapshot_id"].map(cutoff)
        if allowed.isna().any() or (events["event_time"] > allowed).any():
            raise DataValidationError("events cannot occur after their graph snapshot cutoff")
    if data.hyperedges is not None:
        hyperedges = data.hyperedges
        _require_columns(
            hyperedges,
            {"graph_snapshot_id", "hyperedge_id", "hyperedge_type", "node_id"},
            "hyperedges",
        )
        if len(hyperedges) > limits.max_hyperedge_rows:
            raise DataValidationError("hyperedge membership row count exceeds the limit")
        member_keys = set(
            hyperedges[["graph_snapshot_id", "node_id"]]
            .astype(str)
            .itertuples(index=False, name=None)
        )
        if member_keys.difference(node_keys):
            raise DataValidationError("hyperedges must reference nodes in the same snapshot")


def load_bundle(
    source: bytes | bytearray | Path | str,
    limits: DataLimits = DEFAULT_DATA_LIMITS,
) -> BundleData:
    validated: ValidatedBundle = validate_bundle(source)
    raw = io.BytesIO(source) if isinstance(source, (bytes, bytearray)) else Path(source).open("rb")
    with raw, zipfile.ZipFile(raw) as archive:
        specs = validated.metadata.file_specs()
        data = BundleData(
            metadata=validated.metadata,
            samples=_read_table(archive, specs["samples"]),
            nodes=_read_table(archive, specs["nodes"]) if "nodes" in specs else None,
            relations=(
                _read_table(archive, specs["relations"]) if "relations" in specs else None
            ),
            events=_read_table(archive, specs["events"]) if "events" in specs else None,
            hyperedges=(
                _read_table(archive, specs["hyperedges"]) if "hyperedges" in specs else None
            ),
        )
    _validate_samples(data, limits)
    _validate_graph(data, limits)
    capabilities: dict[str, object] = dict(validated.metadata.capabilities())
    reasons: dict[str, str] = {}
    if data.nodes is not None and len(data.nodes) > limits.max_gnn_nodes:
        capabilities["gnn"] = False
        reasons["gnn"] = f"node count exceeds {limits.max_gnn_nodes}"
    if data.relations is not None and len(data.relations) > limits.max_gnn_relations:
        capabilities["gnn"] = False
        reasons["gnn"] = f"relation count exceeds {limits.max_gnn_relations}"
    capabilities["strictFuturePrediction"] = not bool(
        data.metadata.graph and data.metadata.graph.static_experiment_only
    )
    capabilities["disabledReasons"] = reasons
    data.capabilities = capabilities
    data.validation = {
        "valid": True,
        "schemaVersion": 1,
        "files": list(validated.members),
        "compressedBytes": validated.compressed_size,
        "uncompressedBytes": validated.uncompressed_size,
    }
    return data
