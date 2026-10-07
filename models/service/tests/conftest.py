import json
import zipfile

import numpy as np
import pandas as pd
import pytest
from service.adapters.singapore import FEATURES


@pytest.fixture
def export_zip(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    n = 90
    ids = [f"SG-{i:04}" for i in range(n)]
    rng = np.random.default_rng(3)
    values = {name: rng.random(n).astype(np.float32) for name in FEATURES}
    pd.DataFrame({"company_id": ids, **values}).to_parquet(root / "company_attr.parquet")
    pd.DataFrame({"company_id_str": ids, "company_id_int": range(n)}).to_parquet(
        root / "id_map.parquet"
    )
    pd.DataFrame(
        {"company_id": ids, "label": [i % 2 for i in range(n)], "is_labeled": [1] * n}
    ).to_parquet(root / "label.parquet")
    pd.DataFrame(
        {
            "src_id": ids,
            "dst_id": ids[1:] + ids[:1],
            "rel_type": ["SAME_ADDRESS"] * n,
            "weight": [1.0] * n,
        }
    ).to_parquet(root / "edges.parquet")
    pd.DataFrame(
        [
            {
                "seed": seed,
                "node_idx": i,
                "split": "train" if i < 54 else "val" if i < 72 else "test",
            }
            for seed in range(5)
            for i in range(n)
        ]
    ).astype({"split": "category"}).to_parquet(root / "splits_5seed.parquet")
    (root / "feature_config.json").write_text(
        json.dumps(
            {
                "protocol_version": "2.0",
                "protocols": {"A_no_priors": {"numeric_features": FEATURES}},
            }
        )
    )
    (root / "export_meta.json").write_text(json.dumps({"scope": "synthetic"}))
    (root / "load_comrisk.py").write_text("raise RuntimeError('never execute uploads')")
    archive = tmp_path / "data.zip"
    with zipfile.ZipFile(archive, "w") as z:
        for file in root.iterdir():
            z.write(file, "comrisk_export/" + file.name)
    return archive
