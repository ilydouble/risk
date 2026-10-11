"""Deterministic subsets of local real data; never fabricate model samples."""

import json
from pathlib import Path

import duckdb
import pandas as pd

from riskgnn.workbench.artifacts import digest, write_json


def acra_subset(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(config={"threads": 2, "memory_limit": "1GB"}) as db:
        for name in ("company_attr", "label", "id_map", "splits_5seed", "edges"):
            db.read_parquet(str(source / f"{name}.parquet")).create_view(name)
        selected = db.execute("""
            WITH endpoints AS (SELECT src_id AS id FROM edges UNION SELECT dst_id FROM edges),
            ranked AS (
              SELECT m.company_id_str AS company_id, row_number() OVER (
                PARTITION BY s.split,l.label ORDER BY sha256(m.company_id_str)) AS rank
              FROM splits_5seed s JOIN id_map m ON s.node_idx=m.company_id_int
              JOIN label l ON m.company_id_str=l.company_id JOIN endpoints e ON e.id=l.company_id
              WHERE s.seed=0
            ) SELECT company_id FROM ranked WHERE rank<=8
        """).df()
        db.register("selected", selected)
        neighbors = db.execute("""
            SELECT DISTINCT dst_id AS company_id FROM (
              SELECT e.*,row_number() OVER(PARTITION BY src_id ORDER BY sha256(dst_id)) AS rank
              FROM edges e JOIN selected s ON e.src_id=s.company_id
            ) WHERE rank<=2
        """).df()
        chosen = pd.concat([selected, neighbors]).drop_duplicates()
        db.register("chosen", chosen)
        companies = db.execute("""SELECT a.* FROM company_attr a JOIN chosen c USING(company_id)
                                   ORDER BY company_id""").df()
        companies.to_parquet(target / "company_attr.parquet", index=False)
        db.execute("SELECT l.* FROM label l JOIN chosen c USING(company_id)").df().to_parquet(
            target / "label.parquet", index=False
        )
        mapping = pd.DataFrame(
            {"company_id_str": companies.company_id, "company_id_int": range(len(companies))}
        )
        mapping.to_parquet(target / "id_map.parquet", index=False)
        db.register("new_map", mapping)
        db.execute("""SELECT s.seed,s.split,n.company_id_int::INTEGER AS node_idx
            FROM splits_5seed s JOIN id_map m ON s.node_idx=m.company_id_int
            JOIN new_map n USING(company_id_str) ORDER BY seed,node_idx""").df().to_parquet(
            target / "splits_5seed.parquet", index=False
        )
        db.execute("""SELECT e.* FROM edges e JOIN chosen a ON e.src_id=a.company_id
                      JOIN chosen b ON e.dst_id=b.company_id
                      ORDER BY e.src_id,e.dst_id,e.rel_type""").df().to_parquet(
            target / "edges.parquet", index=False
        )
        for name in ("industry", "area", "qualify"):
            db.read_parquet(str(source / f"hypergraph_{name}.parquet")).create_view("members")
            db.execute("SELECT m.* FROM members m JOIN chosen c USING(company_id)").df().to_parquet(
                target / f"hypergraph_{name}.parquet", index=False
            )
    pd.read_parquet(source / "risk_data.parquet").to_parquet(
        target / "risk_data.parquet", index=False
    )
    (target / "feature_config.json").write_bytes((source / "feature_config.json").read_bytes())
    export = json.loads((source / "export_meta.json").read_text())
    export["testSubset"] = {
        "rule": "seed-0 split/label strata, connected company hash order; "
        "eight per stratum plus two neighbors",
        "source": {
            name: digest(source / name)
            for name in (
                "company_attr.parquet",
                "label.parquet",
                "edges.parquet",
                "splits_5seed.parquet",
            )
        },
    }
    write_json(target / "export_meta.json", export)
    # Attachment is copied as data, never imported by the workbench.
    (target / "load_comrisk.py").write_bytes((source / "load_comrisk.py").read_bytes())
