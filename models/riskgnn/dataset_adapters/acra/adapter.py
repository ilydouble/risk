import math
from collections.abc import Iterable
from pathlib import Path

from riskgnn.dataset_adapters.acra.analysis import analyze
from riskgnn.dataset_adapters.acra.paths import data_root
from riskgnn.dataset_adapters.acra.preparation import prepare
from riskgnn.dataset_adapters.acra.validation import (
    FEATURES,
    connect,
    validate,
    verify_validated,
)
from riskgnn.dataset_adapters.base import DatasetAdapter
from riskgnn.dataset_adapters.contract import read_contract
from riskgnn.dataset_adapters.delivery import delivery_for
from riskgnn.dataset_adapters.enterprise import attributes


class SingaporeAdapter(DatasetAdapter):
    id = "sg-comrisk"
    version = "1"
    trainable = True

    def inspect(self, archive: Path, workspace: Path, config: dict) -> dict:
        delivery_for(self.id, self.version).config(config)
        _, relative = read_contract(archive)
        result = validate(archive, workspace)
        root = data_root(workspace)
        if root.resolve() != (workspace / relative).resolve():
            raise ValueError("Dataset files and contract must share the data root")
        result["analysis"] = analyze(root, result)
        result["datasetProfile"] = {
            "datasetFormat": "sg-comrisk-v1",
            "taskType": "entity_snapshot",
            "target": "Singapore corporate distress proxy",
            "features": result["features"],
            "splits": result["splits"],
            "relations": result["relations"],
        }
        return result

    def prepare(self, validated: Path, output: Path, config: dict) -> dict:
        resolved = delivery_for(self.id, self.version).config(config)
        return prepare(validated, output, target_count=int(resolved["target_count"]))

    def enterprise_records(self, validated: Path) -> Iterable[dict]:
        verify_validated(validated)
        with connect(data_root(validated)) as db:
            available = {row[0] for row in db.execute("DESCRIBE company_attr").fetchall()}
            display_fields = [
                name
                for name in (
                    "register_capital",
                    "paid_capital",
                    "setup_time_months",
                    "country",
                    "ssic_code",
                    "ssic2",
                    "age_years",
                )
                if name in available
            ]
            columns = ",".join(f'a."{name}"' for name in FEATURES)
            name_column = 'a."name"' if "name" in available else "NULL"
            display_columns = "".join(f',a."{name}"' for name in display_fields)
            cursor = db.execute(
                f"SELECT a.company_id,{columns},l.label,l.is_labeled,s.split,"
                f"{name_column}{display_columns} "
                "FROM company_attr a LEFT JOIN label l USING(company_id) "
                "LEFT JOIN id_map m USING(company_id) "
                "LEFT JOIN splits_5seed s ON s.node_idx=m.node_idx AND s.seed=0 "
                "ORDER BY a.company_id"
            )
            while rows := cursor.fetchmany(2000):
                for row in rows:
                    yield {
                        "kind": "company",
                        "snapshot": "seed-0",
                        "nodeId": row[0],
                        "data": {
                            "name": row[10],
                            "attributes": attributes(FEATURES, row[1:7]),
                            "properties": {
                                key: None
                                if isinstance(value, float) and not math.isfinite(value)
                                else value
                                for key, value in zip(display_fields, row[11:], strict=True)
                            },
                            "label": int(row[7]) if row[8] else None,
                            "split": row[9],
                        },
                    }
            cursor = db.execute("SELECT * FROM edges ORDER BY src_id,dst_id,rel_type")
            names = [column[0] for column in cursor.description]
            while rows := cursor.fetchmany(2000):
                for row in rows:
                    data = dict(zip(names, row, strict=True))
                    yield {
                        "kind": "edge",
                        "snapshot": "seed-0",
                        "source": data["src_id"],
                        "target": data["dst_id"],
                        "data": data,
                    }
