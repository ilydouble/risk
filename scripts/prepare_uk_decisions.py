"""Export UK research observations as labelled decisions without changing source tables."""

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPLITS = ("train", "valid", "test")
YEARS = {"train": {"2019", "2020"}, "valid": {"2022"}, "test": {"2024"}}
QUESTION_ID = "formal_insolvency_12m"
QUESTION = {
    "type": "choice",
    "instructions": (
        "Predict whether the target company will have a first observed primary formal "
        "insolvency procedure in the next 12 months, in this matched research cohort. "
        "Unlisted features are missing, not zero. Monetary values use the stated currency."
    ),
    "criteria": {
        "no_event": "No primary formal insolvency observed within the next 12 months",
        "event": "Primary formal insolvency observed within the next 12 months",
    },
}


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def encode(data):
    return json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)


def verify(path, expected):
    if digest(path) != expected:
        raise ValueError(f"Source digest mismatch: {path}")


def select_pairs(snapshot, limit, seed):
    pairs = defaultdict(list)
    for node in snapshot["nodes"]:
        pairs[node["properties"]["pair_id"]].append(node)
    for pair in pairs.values():
        if (
            len(pair) != 2
            or {n["label"] for n in pair} != {0, 1}
            or len({n["properties"]["company_id"] for n in pair}) != 2
            or len({n["properties"]["observation_month"] for n in pair}) != 1
        ):
            raise ValueError("Invalid matched pair")
    ordered = sorted(pairs, key=lambda p: hashlib.sha256(f"{seed}:{p}".encode()).hexdigest())
    return [node for pair_id in (ordered[:limit] if limit else ordered) for node in pairs[pair_id]]


def feature_state(row, contract):
    state = {}
    for name in contract["numericFeatureAllowlist"]:
        if name.endswith("_missing") and name != "financial_missing":
            continue
        value = row[name]
        if value == "":
            continue
        elif value in {"True", "False"}:
            state[name] = value == "True"
        else:
            number = float(value)
            if not math.isfinite(number):
                raise ValueError(f"Non-finite feature: {name}")
            state[name] = int(number) if number.is_integer() else number
    for name in contract["categoricalFeatureAllowlist"]:
        if row[name]:
            state[name] = row[name]
    return state


def relationship_summary(snapshot):
    """Use structural facts only; never aggregate neighbours' outcomes or identities."""
    summaries = defaultdict(lambda: {"group_context": {}, "direct_relations": {}})
    months = {n["id"]: n["properties"]["observation_month"] for n in snapshot["nodes"]}
    for group in snapshot["hyperedges"]:
        members = group["members"]
        if len(set(members)) != len(members) or len(members) < 2:
            raise ValueError("Invalid group members")
        if len({months[n] for n in members}) != 1:
            raise ValueError("Relationship context crosses observation months")
        for node_id in members:
            context = summaries[node_id]["group_context"].setdefault(
                group["kind"], {"memberships": 0, "largest_group_peer_count": 0}
            )
            context["memberships"] += 1
            context["largest_group_peer_count"] = max(
                context["largest_group_peer_count"], len(members) - 1
            )
    for edge in snapshot["edges"]:
        if months[edge["source"]] != months[edge["target"]]:
            raise ValueError("Relationship edge crosses observation months")
        for node_id, direction in ((edge["source"], "out"), (edge["target"], "in")):
            context = summaries[node_id]["direct_relations"]
            key = f"{direction}:{edge['relation']}"
            context[key] = context.get(key, 0) + 1
    return summaries


def build(source, output, train_pairs=0, eval_pairs=0, seed=42):
    if output.exists():
        raise ValueError("Choose a new output directory; existing data is never overwritten")
    if min(train_pairs, eval_pairs) < 0:
        raise ValueError("Pair limits must be nonnegative")
    delivery = json.loads((source / "delivery-manifest.json").read_text())
    metadata_path = source / "model-input" / "export_meta.json"
    metadata = json.loads(metadata_path.read_text())
    verify(source / "delivery-manifest.json", metadata["sourceDeliverySha256"])
    inputs = {}
    for name in ("dataset.json", "features.csv", "feature-contract.json", "labels.csv"):
        expected = delivery["files"][name]["sha256"]
        verify(source / name, expected)
        inputs[name] = expected
    contract = json.loads((source / "feature-contract.json").read_text())
    snapshots, selected = {}, {}
    seen_companies, seen_pairs, all_ids = set(), set(), set()
    previous_end = ""
    for split in SPLITS:
        path = source / "model-input" / f"{split}.json"
        expected = metadata["snapshots"][split]["sha256"]
        verify(path, expected)
        inputs[f"model-input/{split}.json"] = expected
        snapshot = json.loads(path.read_text())
        if snapshot["events"] or snapshot["synthetic"]:
            raise ValueError("Source must contain real observations and no event inputs")
        companies, pairs, months, ends, ids = set(), set(), [], [], set()
        for node in snapshot["nodes"]:
            p = node["properties"]
            month = p["observation_month"]
            expected_end = f"{int(month[:4]) + 1:04d}{month[4:]}"
            if (
                node["id"] != p["sample_id"]
                or p["prediction_horizon_months"] != 12
                or month[:4] not in YEARS[split]
                or p["followup_end_month"] != expected_end
                or node["label"] not in (0, 1)
                or node["id"] in ids
            ):
                raise ValueError("Invalid observation identity, horizon or year")
            ids.add(node["id"])
            companies.add(p["company_id"])
            pairs.add(p["pair_id"])
            months.append(month)
            ends.append(p["followup_end_month"])
        if companies & seen_companies or pairs & seen_pairs or ids & all_ids:
            raise ValueError("Company, pair or sample crosses splits")
        if previous_end and previous_end >= min(months):
            raise ValueError("Prediction horizon overlaps the next split")
        previous_end = max(ends)
        seen_companies.update(companies)
        seen_pairs.update(pairs)
        all_ids.update(ids)
        snapshots[split] = snapshot
        selected[split] = select_pairs(
            snapshot, train_pairs if split == "train" else eval_pairs, seed
        )
    wanted = {n["id"]: n for nodes in selected.values() for n in nodes}
    features = {}
    for row in rows(source / "features.csv"):
        sample = row["sample_id"]
        if sample not in wanted:
            continue
        p = wanted[sample]["properties"]
        if (
            row["company_id"] != p["company_id"]
            or row["observation_date"][:7] != p["observation_month"]
            or sample in features
        ):
            raise ValueError("Feature identity mismatch")
        for date_field in ("historical_basic_available_by_assumed",
                           "financial_previous_available_by_assumed"):
            if row[date_field] and row[date_field] > row["observation_date"]:
                raise ValueError("Feature disclosure is after observation")
        features[sample] = feature_state(row, contract)
    if set(features) != set(wanted):
        raise ValueError("Missing feature observations")
    output.mkdir(parents=True)
    report = {
        "format": "uk-labelled-decisions-v1", "seed": seed, "inputs": inputs,
        "featureRepresentation": "Allowlisted observed values; omitted means missing, not zero",
        "exportMetadataSha256": digest(metadata_path),
        "target": QUESTION["instructions"], "splits": {},
        "limitations": [
            "Matched 1:1 research cohort; probabilities are not UK population risk.",
            "Current registry graph approximates history; not historically verified.",
            "Financial availability uses conservative monthly assumptions.",
            "Structural graph coverage has documented cross-year drift.",
            "Existing 2024 holdout has been examined in prior model diagnosis.",
        ],
    }
    index_path = output / "sample-index.jsonl"
    with index_path.open("w") as index:
        for split in SPLITS:
            graph = relationship_summary(snapshots[split])
            for variant in ("financial", "graph"):
                path = output / f"{split}.{variant}.jsonl"
                with path.open("w") as stream:
                    for node in selected[split]:
                        state = {"features": features[node["id"]]}
                        if variant == "graph":
                            state["relationship_summary"] = graph.get(
                                node["id"], {"group_context": {}, "direct_relations": {}}
                            )
                        stream.write(encode({
                            "state": state, "questions": {QUESTION_ID: QUESTION},
                            "expected": {QUESTION_ID: "event" if node["label"] else "no_event"},
                        }) + "\n")
            for line, node in enumerate(selected[split], 1):
                index.write(encode({"split": split, "line": line, **node["properties"]}) + "\n")
            report["splits"][split] = {
                "samples": len(selected[split]),
                "labels": dict(Counter(n["label"] for n in selected[split])),
                "companies": len({n["properties"]["company_id"] for n in selected[split]}),
            }
    report["files"] = {
        p.name: {"sha256": digest(p), "bytes": p.stat().st_size}
        for p in sorted(output.glob("*.jsonl"))
    }
    (output / "manifest.json").write_text(encode(report) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "datasets/uk_research")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--train-pairs", type=int, default=0, help="0 selects all pairs")
    parser.add_argument("--eval-pairs", type=int, default=0, help="0 selects all pairs")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    summary = build(args.source, args.output, args.train_pairs, args.eval_pairs, args.seed)
    print(encode(summary["splits"]))
