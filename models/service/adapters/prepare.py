import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from service.adapters.archive import data_root
from service.adapters.singapore import FEATURES, connect, verify_validated
from service.files import seal, write_json


def prepare(validated: Path, output: Path, *, target_count: int = 2000) -> dict[str, Any]:
    """Deterministic stratified targets plus bounded graph context; original splits survive."""
    source = verify_validated(validated)
    output.mkdir(parents=True, exist_ok=True)
    with connect(data_root(validated)) as db:
        targets = db.execute(
            "SELECT m.company_id,s.split,l.label FROM splits_5seed s "
            "JOIN id_map m USING(node_idx) JOIN label l USING(company_id) WHERE s.seed=0"
        ).df()
        targets["rank"] = targets.company_id.map(
            lambda x: hashlib.sha256(f"smoke-v1:0:{x}".encode()).hexdigest()
        )
        size = min(target_count, len(targets))
        groups = list(targets.groupby(["split", "label"], sort=True))
        if len(groups) != 6:
            raise ValueError("Each split must contain both labels")
        allocations = [min(len(g), max(1, int(size * len(g) / len(targets)))) for _, g in groups]
        while sum(allocations) < size:
            for i, (_, group) in enumerate(groups):
                if allocations[i] < len(group) and sum(allocations) < size:
                    allocations[i] += 1
        selected = pd.concat(
            [
                group.sort_values("rank").head(count)
                for (_, group), count in zip(groups, allocations, strict=True)
            ]
        )
        chosen = set(selected.company_id)
        frontier = chosen.copy()
        sampled: list[pd.DataFrame] = []
        for _ in range(2):
            db.register("frontier", pd.DataFrame({"company_id": sorted(frontier)}))
            neighbors = db.execute("""
                WITH neighbors AS (
                  SELECT e.src_id AS center,e.dst_id AS neighbor,e.rel_type FROM edges e
                    JOIN frontier f ON e.src_id=f.company_id
                  UNION
                  SELECT e.dst_id,e.src_id,e.rel_type FROM edges e
                    JOIN frontier f ON e.dst_id=f.company_id
                ) SELECT * EXCLUDE (rank) FROM (
                  SELECT *,row_number() OVER (PARTITION BY center ORDER BY
                    sha256(center || ':' || neighbor || ':' || rel_type)) AS rank FROM neighbors
                ) WHERE rank<=4 ORDER BY center,rank
            """).df()
            sampled.append(neighbors)
            frontier = set(neighbors.neighbor) - chosen
            chosen.update(frontier)
        db.register("chosen", pd.DataFrame({"company_id": sorted(chosen)}))
        columns = ",".join(f'a."{name}"' for name in FEATURES)
        nodes = db.execute(
            f"SELECT a.company_id,{columns} FROM company_attr a "
            "JOIN chosen c USING(company_id) ORDER BY a.company_id"
        ).df()
    ids = nodes.company_id.astype(str).tolist()
    index = {name: i for i, name in enumerate(ids)}
    selected = selected.sort_values("company_id")
    split = np.full(len(ids), "context", dtype="<U8")
    labels = np.full(len(ids), -1, dtype=np.int64)
    for row in selected.itertuples():
        split[index[row.company_id]], labels[index[row.company_id]] = row.split, int(row.label)
    x = nodes[FEATURES].to_numpy(dtype=np.float32)
    x[~np.isfinite(x)] = np.nan
    train = split == "train"
    statistics: list[float] = []
    for j, name in enumerate(FEATURES):
        available = x[train, j][np.isfinite(x[train, j])]
        value = (
            0.0
            if name != "address_trust"
            else (float(np.median(available)) if len(available) else 0.0)
        )
        statistics.append(value)
        x[~np.isfinite(x[:, j]), j] = value
    edges = pd.concat(sampled).drop_duplicates()
    relation_types = sorted(edges.rel_type.unique().tolist()) or ["SAME_ADDRESS"]
    rel_index = {name: i for i, name in enumerate(relation_types)}
    triples = sorted(
        {(index[r.center], index[r.neighbor], rel_index[r.rel_type]) for r in edges.itertuples()}
        | {(index[r.neighbor], index[r.center], rel_index[r.rel_type]) for r in edges.itertuples()}
    )
    encoded = np.array(triples, dtype=np.int64).reshape(-1, 3)
    np.savez_compressed(
        output / "context.npz", features=x, labels=labels, splits=split, edges=encoded
    )
    write_json(output / "ids.json", ids)
    metadata = {
        "profile": "smoke-v1",
        "sourceSha256": source["sha256"],
        "seed": 0,
        "targetCount": len(selected),
        "nodeCount": len(ids),
        "edgeCount": len(encoded),
        "contextHops": 2,
        "contextFanout": 4,
        "relations": relation_types,
        "features": FEATURES,
        "splitCounts": {name: int(np.sum(split == name)) for name in ("train", "val", "test")},
        "preprocessing": {"fitSplit": "train", "fillValues": statistics},
        "edgePolicy": "bidirectional-unit-weights",
        "protocol": "sg-node-edge-train-fit-v1",
    }
    write_json(output / "metadata.json", metadata)
    seal(output, kind="riskgnn-prepared-v1", metadata={"sourceSha256": source["sha256"]})
    return metadata
