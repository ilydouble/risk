"""Observation-level UK adaptation, leakage boundaries and dynamic graph execution."""

import csv
from copy import deepcopy

import numpy as np
import pytest
import torch
from riskgnn_plus.workbench.network import PortablePlus
from riskgnn_plus.workbench.preparation import prepare as plus_prepare
from riskgnn_plus.workbench.training import train

from riskgnn.dataset_adapters.packaging import package
from riskgnn.dataset_adapters.registry import inspect, resolve
from riskgnn.dataset_adapters.snapshot_io import load
from riskgnn.dataset_adapters.uk_dataset_v1.convert import convert, digest, select, write
from riskgnn.dataset_adapters.uk_dataset_v1.research_schema import HYPEREDGES, POLICY, check
from riskgnn.workbench.artifacts import read_json
from riskgnn.workbench.network import create_model


def table(path, values):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(values[0]))
        writer.writeheader()
        writer.writerows(values)


@pytest.fixture
def research_input(tmp_path):
    source = tmp_path / "research"
    source.mkdir()
    features, labels, nodes, memberships = [], [], [], []
    for year in (2019, 2021, 2022, 2023, 2024):
        for label in (0, 1):
            company, sample = f"{year}{label}", f"sample-{year}-{label}"
            features.append(
                {
                    "sample_id": sample,
                    "company_id": company,
                    "observation_date": f"{year}-01-31",
                    **{
                        n: ("-100" if n == "assets" else "0")
                        for n in POLICY["numericFeatureAllowlist"]
                    },
                    **{
                        n: ("TRAIN" if year == 2019 else "UNSEEN")
                        for n in POLICY["categoricalFeatureAllowlist"]
                    },
                }
            )
            labels.append(
                {
                    "sample_id": sample,
                    "company_id": company,
                    "pair_id": str(year),
                    "label": str(label),
                    "observation_month": f"{year}-01",
                    "followup_end_month": f"{year + 1}-01",
                    "prediction_horizon_months": "12",
                }
            )
            nodes.append({"id": company, "name": "Company " + company})
            memberships.extend({"group_id": kind, "node_id": company} for kind in HYPEREDGES)
    table(source / "features.csv", features)
    table(source / "labels.csv", labels)
    table(source / "nodes.csv", nodes)
    table(
        source / "groups.csv",
        [{"id": kind, "kind": kind, "source_system": "official"} for kind in HYPEREDGES],
    )
    table(source / "group-memberships.csv", memberships)
    (source / "edges.csv").write_text("source,target,relation\n")
    write(source / "feature-contract.json", POLICY)
    write(source / "dataset.json", {"format": "uk-research-dataset-v1"})
    write(
        source / "delivery-manifest.json",
        {"files": {p.name: {"sha256": digest(p)} for p in source.iterdir()}},
    )
    converted = tmp_path / "input"
    convert(source, converted)
    return converted


def test_convert_masks_events_preserves_negative_values_and_train_vocabulary(research_input):
    snapshots = load(research_input)
    policy = read_json(research_input / "feature-policy.json")
    check(snapshots, policy)
    assert all(values == ["TRAIN"] for values in policy["categories"].values())
    for snapshot in snapshots.values():
        assert not snapshot.events and len(snapshot.hyperedges) == 15 and not snapshot.edges
        assert snapshot.nodes[0].features[snapshot.feature_names.index("assets")] == -100
    valid = snapshots["valid"]
    assert (
        valid.nodes[0].features[valid.feature_names.index("cat:financial_currency:__unknown__")]
        == 1
    )
    audit = list(csv.DictReader((research_input / "split-audit.csv").open()))
    assert sum(r["reason"] == "12_month_horizon_embargo" for r in audit) == 4


def test_split_removes_whole_pair_when_company_reappears():
    rows = []
    for year in (2019, 2022, 2024):
        for label in ("0", "1"):
            rows.append(
                {
                    "sample_id": f"{year}-{label}",
                    "pair_id": str(year),
                    "label": label,
                    "company_id": "repeated" if label == "0" else str(year),
                    "observation_month": f"{year}-01",
                }
            )
    splits, excluded = select(rows)
    assert len(splits["test"]) == 2 and not splits["valid"] and not splits["train"]
    assert len(excluded) == 4


def test_research_schema_rejects_company_overlap_and_horizon_changes(research_input):
    snapshots = load(research_input)
    policy = read_json(research_input / "feature-policy.json")
    broken = deepcopy(snapshots)
    broken["test"].nodes[0].properties["company_id"] = (
        snapshots["train"].nodes[0].properties["company_id"]
    )
    with pytest.raises(ValueError, match="crosses"):
        check(broken, policy)
    broken = deepcopy(snapshots)
    broken["train"].nodes[0].properties["followup_end_month"] = "2024-01"
    with pytest.raises(ValueError, match="horizon"):
        check(broken, policy)


def test_research_schema_rejects_event_features_and_misaligned_pairs(research_input):
    snapshots = load(research_input)
    policy = read_json(research_input / "feature-policy.json")
    poisoned = deepcopy(policy)
    poisoned["numeric"].append("target_event_month")
    with pytest.raises(ValueError, match="allowlist"):
        check(snapshots, poisoned)
    broken = deepcopy(snapshots)
    node = broken["train"].nodes[0]
    node.properties["observation_month"] = "2019-02"
    node.properties["followup_end_month"] = "2020-02"
    for other in broken["train"].nodes[1:]:
        other.properties["pair_id"] = node.properties["pair_id"]
    with pytest.raises(ValueError, match="pair"):
        check(broken, policy)


def test_new_uk_preset_prepares_fifteen_channels_and_trains_empty_edge_graph(
    research_input, tmp_path
):
    archive = tmp_path / "input.zip"
    package(research_input, archive, "uk-companies", "research-test", overrides={"target_count": 6})
    result = inspect(archive, tmp_path / "validated")
    assert result["datasetProfile"]["taskType"] == "entity_observation"
    adapter, contract = resolve(archive)
    assert adapter.version == "2"
    prepared = tmp_path / "prepared"
    meta = plus_prepare(adapter, tmp_path / "validated", prepared, contract["adapter"]["config"])
    assert len(meta["hyperedgeTypes"]) == 15 and meta["eventCount"] == 0
    assert meta["edgeCount"] == 0 and meta["incidenceCount"] == 90
    context = dict(np.load(prepared / "context.npz", allow_pickle=False))
    assert np.isfinite(context["features"]).all()
    targets = np.flatnonzero(context["splits"] == "train").tolist()
    model = PortablePlus(meta, context, {})
    output = model(targets)
    output.primary_logits.sum().backward()
    gradient = model.core.hypergnn.proj.weight.grad
    assert gradient is not None and torch.isfinite(gradient).all() and gradient.abs().sum() > 0
    model.eval()
    with torch.no_grad():
        expected = model(targets).probabilities
        changed = deepcopy(context)
        changed["features"][context["splits"] != "train"] += 100
        isolated = PortablePlus(meta, changed, {}).eval()
        isolated.load_state_dict(model.state_dict())
        assert torch.allclose(expected, isolated(targets).probabilities)
    # The existing RiskGNN node_edge path also accepts the new feature width and no edges.
    base_meta = {**meta, "architecture": "dataset-node-edge-v1"}
    base = create_model(base_meta, len(context["features"]))
    prediction = base(
        context["features"],
        torch.tensor(targets),
        torch.empty((0, 2), dtype=torch.long),
        torch.empty(0, dtype=torch.long),
        len(targets),
        torch.empty(0),
        torch.empty(0),
    )
    assert torch.isfinite(prediction).all()
    trained = train(prepared, tmp_path / "model", 1)
    assert trained["selectedEpoch"] == 1
    assert trained["architecture"] == "riskgnn-plus-adaptive-v1"
    from riskgnn.workbench.predictor import Predictor
    from riskgnn.workbench.training import evaluate

    predictor = Predictor(tmp_path / "model")
    ids = list(predictor.index)[:2]
    expected = predictor.predict(ids)
    reloaded = Predictor(tmp_path / "model")
    assert reloaded.predict(ids[::-1]) == expected[::-1]
    report = evaluate(tmp_path / "model", output=tmp_path / "report")
    assert report["independentReload"] and report["metrics"]["count"] == 2
