"""Build calibrated synthetic edge-confidence scenarios for SMEsD.

The original SMEsD pickle files are treated as immutable inputs.  Relations 0-11
form six exact forward/reverse pairs; this script stores one row per logical pair
and reconstructs directed edges at training time.  Labels are never read.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

SCHEMA_VERSION = "smesd-edge-uncertainty-v3"
SPLIT_FILES = {
    "train": "train_data.pkl",
    "valid": "validate_data.pkl",
    "test": "test_data.pkl",
}
AUXILIARY_FILES = {
    "metaEmbedding": "meta_emb.pkl",
    "splitIndices": "split_data_idx.pkl",
}
FORWARD_TYPES = (0, 2, 4, 6, 8, 10)
RELATION_DOMAINS = {
    0: ("company", "person"),
    2: ("company", "person"),
    4: ("company", "person"),
    6: ("company", "company"),
    8: ("person", "company"),
    10: ("company", "company"),
}
ADDED_CONFIDENCE_MIN = np.float32(0.05)
ADDED_CONFIDENCE_MAX = np.float32(0.20)


@dataclass(frozen=True)
class LogicalPairs:
    source: np.ndarray
    target: np.ndarray
    relation: np.ndarray
    strength: np.ndarray

    def __len__(self) -> int:
        return int(self.source.shape[0])


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _node_kind(node: int, company_count: int) -> str:
    return "company" if node < company_count else "person"


def extract_logical_pairs(
    graph: tuple[object, object, object], company_count: int
) -> LogicalPairs:
    edge_index, edge_type, edge_weight = graph
    edges = np.asarray(edge_index, dtype=np.int64)
    relations = np.asarray(edge_type, dtype=np.int64)
    strengths = np.asarray(edge_weight, dtype=np.float32)
    if edges.ndim != 2 or edges.shape[1] != 2:
        raise ValueError("edge_index must have shape [n_edges, 2]")
    if not (len(edges) == len(relations) == len(strengths)):
        raise ValueError("edge_index, edge_type and edge_weight lengths differ")

    used = relations < 12
    directed = {
        (int(source), int(target), int(relation), float(strength))
        for (source, target), relation, strength in zip(
            edges[used], relations[used], strengths[used], strict=True
        )
    }
    forward_rows: list[tuple[int, int, int, float]] = []
    for (source, target), relation, strength in zip(
        edges[used], relations[used], strengths[used], strict=True
    ):
        relation = int(relation)
        if relation not in FORWARD_TYPES:
            continue
        row = (int(source), int(target), relation, float(strength))
        reverse = (row[1], row[0], relation + 1, row[3])
        if reverse not in directed:
            raise ValueError(f"missing reverse edge for {row}")
        expected_source, expected_target = RELATION_DOMAINS[relation]
        if _node_kind(row[0], company_count) != expected_source:
            raise ValueError(f"invalid source domain for {row}")
        if _node_kind(row[1], company_count) != expected_target:
            raise ValueError(f"invalid target domain for {row}")
        forward_rows.append(row)

    if len(forward_rows) * 2 != int(used.sum()):
        raise ValueError("relations 0-11 are not exact forward/reverse pairs")
    if len({row[:3] for row in forward_rows}) != len(forward_rows):
        raise ValueError("duplicate logical relation pair in source graph")

    rows = np.asarray(forward_rows, dtype=object)
    return LogicalPairs(
        source=rows[:, 0].astype(np.int64),
        target=rows[:, 1].astype(np.int64),
        relation=rows[:, 2].astype(np.int64),
        strength=rows[:, 3].astype(np.float32),
    )


def assign_observation_confidence(
    clean: LogicalPairs,
    false: LogicalPairs,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Keep true edges certain and sample low confidence for added false edges."""
    true_confidence = np.ones(len(clean), dtype=np.float32)
    false_confidence = rng.uniform(
        float(ADDED_CONFIDENCE_MIN),
        float(ADDED_CONFIDENCE_MAX),
        size=len(false),
    ).astype(np.float32)
    return true_confidence, false_confidence


def generate_false_pairs(
    clean: LogicalPairs, noise_ratio: float, rng: np.random.Generator
) -> LogicalPairs:
    sources: list[int] = []
    targets: list[int] = []
    relations: list[int] = []
    strengths: list[float] = []
    for relation in FORWARD_TYPES:
        mask = clean.relation == relation
        relation_sources = clean.source[mask]
        relation_targets = clean.target[mask]
        requested = round(len(relation_sources) * noise_ratio)
        existing = {
            (int(source), int(target))
            for source, target in zip(relation_sources, relation_targets, strict=True)
        }
        generated: set[tuple[int, int]] = set()
        attempts = 0
        max_attempts = max(10_000, requested * 500)
        while len(generated) < requested and attempts < max_attempts:
            source = int(rng.choice(relation_sources))
            target = int(rng.choice(relation_targets))
            candidate = (source, target)
            attempts += 1
            if source == target or candidate in existing or candidate in generated:
                continue
            generated.add(candidate)
        if len(generated) != requested:
            raise RuntimeError(
                f"could only generate {len(generated)}/{requested} false pairs "
                f"for relation {relation}"
            )
        ordered = sorted(generated)
        sources.extend(source for source, _ in ordered)
        targets.extend(target for _, target in ordered)
        relations.extend([relation] * requested)
        strengths.extend([1.0] * requested)

    return LogicalPairs(
        source=np.asarray(sources, dtype=np.int64),
        target=np.asarray(targets, dtype=np.int64),
        relation=np.asarray(relations, dtype=np.int64),
        strength=np.asarray(strengths, dtype=np.float32),
    )


def build_scenario(
    clean: LogicalPairs, noise_ratio: float, rng: np.random.Generator
) -> dict[str, np.ndarray]:
    false = generate_false_pairs(clean, noise_ratio, rng)
    true_confidence, false_confidence = assign_observation_confidence(clean, false, rng)
    source = np.concatenate((clean.source, false.source))
    target = np.concatenate((clean.target, false.target))
    relation = np.concatenate((clean.relation, false.relation))
    strength = np.concatenate((clean.strength, false.strength))
    confidence = np.concatenate((true_confidence, false_confidence))
    is_true = np.concatenate(
        (np.ones(len(clean), dtype=np.bool_), np.zeros(len(false), dtype=np.bool_))
    )
    order = rng.permutation(len(source))
    return {
        "source": source[order],
        "target": target[order],
        "relation": relation[order],
        "strength": strength[order],
        "confidence": confidence[order],
        "is_true": is_true[order],
    }


def calibration_summary(scenario: dict[str, np.ndarray]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    confidence = scenario["confidence"]
    is_true = scenario["is_true"]
    for value in sorted({float(item) for item in confidence}):
        mask = np.isclose(confidence, value)
        rows.append(
            {
                "confidence": value,
                "candidatePairs": int(mask.sum()),
                "truePairs": int(is_true[mask].sum()),
                "empiricalTrueRate": float(is_true[mask].mean()),
            }
        )
    return rows


def build_dataset(
    data_dir: Path, output_dir: Path, noise_ratio: float, seed: int
) -> dict[str, object]:
    if not 0 <= noise_ratio <= 0.8:
        raise ValueError("noise_ratio must be within [0, 0.8]")
    meta_embedding = pd.read_pickle(data_dir / "meta_emb.pkl")
    company_count = int(np.asarray(meta_embedding[0]).shape[0])
    person_count = int(np.asarray(meta_embedding[1]).shape[0])
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, object] = {
        "schemaVersion": SCHEMA_VERSION,
        "simulationSeed": seed,
        "noiseRatio": noise_ratio,
        "noiseRatioDefinition": "added_false_pairs / original_true_pairs",
        "additionRatio": noise_ratio,
        "retainedDeletionRatio": 0.0,
        "usesLabels": False,
        "companyCount": company_count,
        "personCount": person_count,
        "addedEdgeConfidenceDistribution": "uniform",
        "addedEdgeConfidenceMin": float(ADDED_CONFIDENCE_MIN),
        "addedEdgeConfidenceMax": float(ADDED_CONFIDENCE_MAX),
        "sourceFiles": {
            name: {"file": filename, "sha256": file_sha256(data_dir / filename)}
            for name, filename in (SPLIT_FILES | AUXILIARY_FILES).items()
        },
        "splits": {},
    }

    for offset, (name, filename) in enumerate(SPLIT_FILES.items()):
        graph = pd.read_pickle(data_dir / filename)[2]
        clean = extract_logical_pairs(graph, company_count)
        scenario = build_scenario(
            clean, noise_ratio, np.random.default_rng(seed + offset * 1_000_003)
        )
        target = output_dir / f"{name}_pairs.npz"
        np.savez_compressed(target, **scenario)
        manifest["splits"][name] = {
            "file": target.name,
            "sha256": file_sha256(target),
            "truePairs": int(scenario["is_true"].sum()),
            "falsePairs": int((~scenario["is_true"]).sum()),
            "retainedDeletionPairs": 0,
            "candidatePairs": len(scenario["source"]),
            "directedEdges": int(len(scenario["source"]) * 2),
            "confidenceComposition": calibration_summary(scenario),
        }

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--noise-ratio", type=float, required=True)
    parser.add_argument("--seed", type=int, default=14)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = build_dataset(
        args.data_dir.resolve(), args.output_dir.resolve(), args.noise_ratio, args.seed
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
