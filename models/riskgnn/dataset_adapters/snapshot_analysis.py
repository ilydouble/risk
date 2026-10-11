"""Shared report mechanics for the two concrete JSON snapshot datasets."""

from pathlib import Path

import numpy as np
import pandas as pd

from riskgnn.dataset_adapters.report import normalize
from riskgnn.dataset_adapters.snapshot_io import load
from riskgnn.dataset_adapters.statistics import psi, safe_number


def analyze(root: Path, manifest: dict) -> dict:
    snapshots = load(root)
    frames = {
        split: pd.DataFrame(
            [n.features for n in snapshot.nodes if n.kind == "company"],
            columns=snapshot.feature_names,
        )
        for split, snapshot in snapshots.items()
    }
    combined = pd.concat(frames.values(), ignore_index=True)
    columns = []
    for name in combined:
        series = combined[name]
        missing = int(series.isna().sum())
        columns.append(
            {
                "name": name,
                "kind": "numeric",
                "missingCount": missing,
                "missingRate": missing / len(combined),
                "uniqueCount": int(series.nunique()),
                "constant": series.nunique() <= 1,
            }
        )
    return normalize(
        {
            "quality": {"rowCount": len(combined), "columns": columns},
            "splits": {
                "validation" if row["split"] == "valid" else row["split"]: {
                    "rows": row["count"],
                    "positives": row["positives"],
                    "positiveRate": row["positives"] / row["count"],
                }
                for row in manifest["splits"]
            },
            "drift": {
                "validation" if split == "valid" else split: [
                    {
                        "name": name,
                        "psi": safe_number(
                            psi(
                                frames["train"][name].astype(np.float64),
                                frame[name].astype(np.float64),
                            )
                        ),
                    }
                    for name in combined
                ]
                for split, frame in frames.items()
                if split != "train"
            },
            "graph": {
                "nodes": len(combined) + manifest["counts"]["persons"],
                "relations": manifest["counts"]["edges"],
                "hyperedges": manifest["counts"]["hyperedges"],
                "events": manifest["counts"]["events"],
            },
        },
        total_rows=len(combined),
    )
