"""Full-column quality scan; drift uses an explicit deterministic bounded sample."""

from pathlib import Path

import numpy as np
import pandas as pd

from service.adapters.singapore import FEATURES, connect
from service.analysis.bundle import _psi, _safe_number
from service.analysis.report import normalize


def analyze(root: Path, manifest: dict) -> dict:
    columns = []
    with connect(root) as db:
        total = manifest["counts"]["company_attr"]
        for name in FEATURES:
            row = db.execute(f'''
                SELECT count(*) FILTER (WHERE "{name}" IS NULL OR NOT isfinite("{name}"::DOUBLE)),
                    count(DISTINCT "{name}") FILTER (WHERE isfinite("{name}"::DOUBLE))
                FROM company_attr
            ''').fetchone()
            assert row is not None
            missing, distinct = row
            columns.append(
                {
                    "name": name,
                    "kind": "numeric",
                    "missingCount": missing,
                    "missingRate": missing / max(total, 1),
                    "uniqueCount": distinct,
                    "constant": distinct <= 1,
                }
            )
        fields = ",".join(f'a."{name}"' for name in FEATURES)
        frame = db.execute(f"""
            SELECT {fields},s.split FROM company_attr a JOIN id_map m USING(company_id)
            JOIN splits_5seed s USING(node_idx) WHERE s.seed=0
            QUALIFY row_number() OVER (PARTITION BY s.split ORDER BY sha256(a.company_id))<=5000
        """).df()
    frame = frame.replace([np.inf, -np.inf], np.nan)
    train = frame[frame.split == "train"]
    drift = {}
    for split, output_name in (("val", "validation"), ("test", "test")):
        other = frame[frame.split == split]
        drift[output_name] = [
            {
                "name": name,
                "psi": _safe_number(
                    _psi(
                        pd.to_numeric(train[name]).astype(float),
                        pd.to_numeric(other[name]).astype(float),
                    )
                ),
            }
            for name in FEATURES
        ]
    splits = {
        ("validation" if item["split"] == "val" else item["split"]): {
            "rows": item["count"],
            "positives": item["positives"],
            "positiveRate": item["positives"] / max(item["count"], 1),
        }
        for item in manifest["splits"]
        if item["seed"] == 0
    }
    result = normalize(
        {
            "quality": {"rowCount": total, "columns": columns},
            "splits": splits,
            "drift": drift,
            "graph": {"nodes": total, "relations": manifest["counts"]["edges"]},
        },
        total_rows=total,
        scope="full_quality_sampled_drift",
    )
    result["driftSampleRows"] = {
        name: int((frame.split == split).sum())
        for name, split in (("train", "train"), ("validation", "val"), ("test", "test"))
    }
    return result
