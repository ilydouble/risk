"""Load the SMEsD corporate-risk benchmark into the shared benchmark structure.

SMEsD ships as five pickles (train/valid/test tuples, split indices, node2index and
the pretrained metapath2vec embeddings).  The training tuple is
``(risk_events, company_attr, graph, hypergraph, label)`` where ``graph`` is already
an ``(edge_index, edge_type, edge_weight)`` triple over global company indices and
``hypergraph`` maps each attribute kind to ``{group: [members]}``.

This loader reshapes that into the same dictionary the UK loader returns, so the
shared trainer can treat both datasets identically.  Unlike the UK snapshot the
three splits share one node universe here, and ``person_emb`` is non-empty (SMEsD
carries person nodes in the heterogeneous graph).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

SPLIT_FILES = (
    ("train", "train_data.pkl"),
    ("valid", "validate_data.pkl"),
    ("test", "test_data.pkl"),
)
SPLIT_ORDER = ("train", "valid", "cal", "test")
HYPEREDGE_KINDS = ("industry", "area", "qualify")
FEATURE_NAMES = ("register_capital", "paid_capital", "age_months")


def _invert_groups(groups: dict) -> dict[int, str]:
    return {int(member): name for name, members in groups.items() for member in members}


def load_smesd_benchmark(
    data_dir: Path,
    *,
    calib_fraction: float = 0.5,
    calib_seed: int = 42,
) -> dict:
    """Read SMEsD pickles into the shared benchmark dictionary."""
    data_dir = Path(data_dir)
    payloads: dict[str, tuple] = {}
    source_sha256: dict[str, str] = {}
    for name, filename in SPLIT_FILES:
        path = data_dir / filename
        if not path.is_file():
            raise FileNotFoundError(f"missing SMEsD split: {path}")
        payloads[name] = pd.read_pickle(path)
        source_sha256[filename] = hashlib.sha256(path.read_bytes()).hexdigest()

    train_idx, valid_idx, test_idx = pd.read_pickle(data_dir / "split_data_idx.pkl")
    com_emb, per_emb = pd.read_pickle(data_dir / "meta_emb.pkl")
    company_num = len(com_emb)

    indices = {
        "train": np.asarray(train_idx, dtype=np.int64),
        "valid": np.asarray(valid_idx, dtype=np.int64),
        "test": np.asarray(test_idx, dtype=np.int64),
    }

    raw_hyper = {name: payloads[name][3] for name in ("train", "valid", "test")}
    splits: dict[str, dict] = {}
    for name in ("train", "valid", "test"):
        risk, attr, graph, _hyper, label = payloads[name]
        community_map = _invert_groups(raw_hyper[name][HYPEREDGE_KINDS[1]])
        idx = indices[name]
        splits[name] = {
            "idx": idx,
            "attr": np.asarray(attr, dtype=np.float32),
            "y": np.asarray(label, dtype=np.int64),
            "community": [community_map.get(int(i), "未知") for i in idx],
            "graph": (
                np.asarray(graph[0], dtype=np.int64),
                np.asarray(graph[1], dtype=np.int64),
                np.asarray(graph[2], dtype=np.float32),
            ),
            "snapshot": name,
            "risk": risk,
        }

    # Mirror the UK protocol: halve validation into model-selection and calibration.
    valid_idx_full = splits["valid"]["idx"]
    permutation = np.random.RandomState(calib_seed).permutation(len(valid_idx_full))
    n_cal = int(round(len(valid_idx_full) * calib_fraction))
    cal_positions = permutation[:n_cal]
    valid_positions = permutation[n_cal:]
    splits["cal"] = {
        "idx": valid_idx_full[cal_positions],
        "attr": splits["valid"]["attr"][cal_positions],
        "y": splits["valid"]["y"][cal_positions],
        "community": [splits["valid"]["community"][int(p)] for p in cal_positions],
        "graph": splits["valid"]["graph"],
        "snapshot": "valid",
        "risk": splits["valid"]["risk"],
    }
    splits["valid"] = {
        "idx": valid_idx_full[valid_positions],
        "attr": splits["valid"]["attr"][valid_positions],
        "y": splits["valid"]["y"][valid_positions],
        "community": [splits["valid"]["community"][int(p)] for p in valid_positions],
        "graph": splits["valid"]["graph"],
        "snapshot": "valid",
        "risk": splits["valid"]["risk"],
    }

    hypergraphs = {
        name: [raw_hyper[splits[name]["snapshot"]][kind] for kind in HYPEREDGE_KINDS]
        for name in SPLIT_ORDER
    }

    return {
        "name": "smesd",
        "feature_names": list(FEATURE_NAMES),
        "relation_names": [f"relation_{i}" for i in range(12)],
        "hyperedge_kinds": list(HYPEREDGE_KINDS),
        "log_features": (),
        "company_num": company_num,
        "person_num": len(per_emb),
        "cause_type_num": 11,
        "court_type_num": 4,
        "category_num": 4,
        "time_label_num": 5,
        "com_emb": np.asarray(com_emb, dtype=np.float32),
        "per_emb": np.asarray(per_emb, dtype=np.float32),
        "node_ids": [str(i) for i in range(company_num)],
        "splits": splits,
        "hypergraphs": hypergraphs,
        "uniform_weights": False,
        "max_nodes": None,
        "hete_scalar_weights": None,
        "standardized": False,
        "source_sha256": source_sha256,
    }


def summarize(dataset: dict) -> dict:
    """Compact description for the run manifest and logs."""
    return {
        "name": dataset["name"],
        "company_num": dataset["company_num"],
        "person_num": dataset["person_num"],
        "features": dataset["feature_names"],
        "relations": dataset["relation_names"],
        "hyperedge_kinds": dataset["hyperedge_kinds"],
        "split_sizes": {name: int(len(split["y"])) for name, split in dataset["splits"].items()},
        "positive_rate": {
            name: float(np.mean(split["y"])) if len(split["y"]) else 0.0
            for name, split in dataset["splits"].items()
        },
        "edge_counts": {
            name: int(split["graph"][0].shape[0]) for name, split in dataset["splits"].items()
        },
    }
