"""Convert the unified research tables to compact, isolated UK training snapshots."""

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

from riskgnn.dataset_adapters.snapshot_schema import Snapshot
from riskgnn.dataset_adapters.uk_dataset_v1.research_schema import (
    HYPEREDGES,
    POLICY,
    RELATIONS,
    TARGET,
    YEARS,
    feature_names,
)

ROOT = Path(__file__).resolve().parents[4]


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":")))


def select(labels):
    pairs = defaultdict(list)
    for row in labels:
        pairs[row["pair_id"]].append(row)
    for pair in pairs.values():
        if (
            len(pair) != 2
            or {r["label"] for r in pair} != {"0", "1"}
            or len({r["observation_month"] for r in pair}) != 1
        ):
            raise ValueError("Invalid matched source pair")
    chosen, reasons, seen = {}, {}, set()
    # Reserve the independent test companies first, without looking at their features/outcomes.
    for split in ("test", "valid", "train"):
        candidates = [p for p in pairs.values() if p[0]["observation_month"][:4] in YEARS[split]]
        keep = [p for p in candidates if not any(r["company_id"] in seen for r in p)]
        selected = {r["sample_id"] for p in keep for r in p}
        chosen[split] = [r for p in keep for r in p]
        for pair in candidates:
            for row in pair:
                if row["sample_id"] not in selected:
                    reasons[row["sample_id"]] = "company_overlap_with_later_split_pair_removed"
        seen.update(r["company_id"] for p in keep for r in p)
    for pair in pairs.values():
        if pair[0]["observation_month"][:4] not in set.union(*YEARS.values()):
            reasons.update({r["sample_id"]: "12_month_horizon_embargo" for r in pair})
    return chosen, reasons


def finite(value, name):
    if value == "":
        return None
    if value in {"True", "False"}:
        return float(value == "True")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"Non-finite UK feature: {name}")
    return result


def convert(source, output):
    if output.exists():
        raise ValueError("Choose a new model-input directory; source data is immutable")
    required = [
        "dataset.json",
        "features.csv",
        "labels.csv",
        "nodes.csv",
        "edges.csv",
        "groups.csv",
        "group-memberships.csv",
        "feature-contract.json",
    ]
    upstream = json.loads((source / "delivery-manifest.json").read_text())
    for name in required:
        if digest(source / name) != upstream["files"][name]["sha256"]:
            raise ValueError("Research source changed: " + name)
    declared = json.loads((source / "feature-contract.json").read_text())
    for key, values in POLICY.items():
        if declared[key] != values:
            raise ValueError("Research feature policy differs from adapter policy")
    labels = list(rows(source / "labels.csv"))
    if len({r["sample_id"] for r in labels}) != len(labels):
        raise ValueError("Duplicate source observation identity")
    if any(r["prediction_horizon_months"] != "12" for r in labels):
        raise ValueError("UK requires the 12-month prediction horizon")
    selected, excluded = select(labels)
    wanted = {r["sample_id"]: r for split in selected.values() for r in split}
    feature_rows = {}
    for row in rows(source / "features.csv"):
        if row["sample_id"] in wanted:
            label = wanted[row["sample_id"]]
            if (
                row["company_id"] != label["company_id"]
                or row["observation_date"][:7] != label["observation_month"]
            ):
                raise ValueError("Observation feature/label identity mismatch")
            if row["sample_id"] in feature_rows:
                raise ValueError("Duplicate observation features")
            feature_rows[row["sample_id"]] = row
    if feature_rows.keys() != wanted.keys():
        raise ValueError("Missing selected observation features")
    categories = {
        name: sorted(
            {
                feature_rows[r["sample_id"]][name]
                for r in selected["train"]
                if feature_rows[r["sample_id"]][name]
            }
        )
        for name in POLICY["categoricalFeatureAllowlist"]
    }
    policy = {
        "numeric": POLICY["numericFeatureAllowlist"],
        "categories": categories,
        "signedLog1p": [n for n in POLICY["numericFeatureAllowlist"] if not n.endswith("_missing")],
        "fitSplit": "train",
        "categoricalEncoding": "train-vocabulary-one-hot-with-unknown",
    }
    names = feature_names(policy)
    company_names = {r["id"]: r["name"] for r in rows(source / "nodes.csv")}
    membership = defaultdict(list)
    for row in rows(source / "group-memberships.csv"):
        membership[row["group_id"]].append(row["node_id"])
    groups = list(rows(source / "groups.csv"))
    relations = list(rows(source / "edges.csv"))
    output.mkdir(parents=True)
    summaries = {}
    for split in ("train", "valid", "test"):
        nodes, by_company = [], defaultdict(dict)
        for label in selected[split]:
            sample, company, month = (
                label["sample_id"],
                label["company_id"],
                label["observation_month"],
            )
            row = feature_rows.pop(sample)
            values = [finite(row[n], n) for n in policy["numeric"]]
            for name, vocab in categories.items():
                value = row[name]
                values.extend(float(value == item) for item in vocab)
                values.append(float(value not in vocab))
            nodes.append(
                {
                    "id": sample,
                    "kind": "company",
                    "name": company_names.get(company),
                    "community": "UK",
                    "features": values,
                    "label": int(label["label"]),
                    "split": split,
                    "properties": {
                        k: label[k]
                        for k in (
                            "sample_id",
                            "company_id",
                            "pair_id",
                            "observation_month",
                            "followup_end_month",
                        )
                    }
                    | {"prediction_horizon_months": 12},
                }
            )
            if month in by_company[company]:
                raise ValueError("Duplicate company/month source observations")
            by_company[company][month] = sample
        edges, hyperedges = [], []
        for relation in relations:
            left, right = by_company[relation["source"]], by_company[relation["target"]]
            if relation["relation"] not in RELATIONS:
                raise ValueError("Unknown source relation")
            for month in left.keys() & right.keys():
                edges.append(
                    {
                        "source": left[month],
                        "target": right[month],
                        "relation": relation["relation"],
                        "weight": 1.0,
                    }
                )
        for group in groups:
            if group["kind"] not in HYPEREDGES:
                raise ValueError("Unknown source hyperedge type")
            by_month = defaultdict(list)
            for company in membership[group["id"]]:
                for month, sample in by_company.get(company, {}).items():
                    by_month[month].append(sample)
            for members in by_month.values():
                if len(members) >= 2:
                    hyperedges.append(
                        {
                            "kind": group["kind"],
                            "members": sorted(members),
                            "source_system": group["source_system"],
                        }
                    )
        data = {
            "schema_version": 1,
            "name": "UK research " + split,
            "synthetic": False,
            "evaluation": "isolated_snapshots",
            "target_description": TARGET,
            "feature_names": names,
            "relation_names": RELATIONS,
            "hyperedge_types": HYPEREDGES,
            "nodes": nodes,
            "edges": edges,
            "hyperedges": hyperedges,
            "events": [],
        }
        # Bound memory here; inspect performs the cross-split checks.
        Snapshot.model_validate(data)
        write(output / f"{split}.json", data)
        summaries[split] = {
            "sha256": digest(output / f"{split}.json"),
            "observations": len(nodes),
            "edges": len(edges),
            "hyperedges": len(hyperedges),
            "memberships": sum(len(h["members"]) for h in hyperedges),
        }
    write(output / "feature-policy.json", policy)
    with (output / "split-audit.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["sample_id", "company_id", "observation_month", "split", "reason"])
        assignment = {r["sample_id"]: sp for sp, rs in selected.items() for r in rs}
        for row in labels:
            writer.writerow(
                [
                    row["sample_id"],
                    row["company_id"],
                    row["observation_month"],
                    assignment.get(row["sample_id"], "excluded"),
                    excluded.get(row["sample_id"], "selected"),
                ]
            )
    meta = {
        "snapshots": summaries,
        "sourceDeliverySha256": digest(source / "delivery-manifest.json"),
        "inputDigests": {n: digest(output / n) for n in ("feature-policy.json", "split-audit.csv")},
        "researchAssumption": {
            "currentRegistryApproximatesHistory": True,
            "historicalGraphVerified": False,
            "eventsAsInputs": False,
            "contextIsSameObservationMonthOnly": True,
        },
        "featureCount": len(names),
        "excludedObservations": len(excluded),
    }
    write(output / "audit.json", meta)
    write(output / "export_meta.json", meta)
    return meta


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "datasets/uk_research")
    parser.add_argument("--output", type=Path, default=ROOT / "datasets/uk_research/model-input")
    args = parser.parse_args()
    print(json.dumps(convert(args.source, args.output)))
