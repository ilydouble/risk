"""Training, independent evaluation, and published voting agree on bound enterprises."""

import numpy as np
import pytest

from model_service.execution.contracts import Operation, OperationRequest, OperationResult
from model_service.execution.contracts.validation import validate_result
from model_service.execution.runtime import runtime_spec
from model_service.modules.models.api.schemas import ResponsePredict
from riskgnn.dataset_adapters.packaging import package
from riskgnn.workbench.artifacts import asset_digest, read_json
from riskgnn.workbench.comparison import FORMAT, classification_metrics
from riskgnn.workbench.graph_to_state import transform
from riskgnn.workbench_cli import execute


@pytest.mark.parametrize("dataset", ["smesd", "acra"])
def test_graph_candidate_models_and_vote_share(dataset, datasets, request, tmp_path):
    if dataset == "smesd":
        archive = tmp_path / "smesd.zip"
        package(datasets / "comrisk_export_v5/smesd", archive, "smesd", "comparison-test")
    else:
        archive = request.getfixturevalue("export_zip")
    algorithms = ["riskgnn-plus", "gcn", "rgcn", "hgt", "g2s-gbdt"]
    train_dir = tmp_path / "train"
    trained = execute(
        {
            "operation": "train",
            "inputs": {"dataset": {"path": str(archive)}},
            "parameters": {"epochs": 1, "dataset": {"target_count": 60}, "comparison": algorithms},
        },
        train_dir,
        lambda _: None,
    )
    validate_result(
        runtime_spec(),
        OperationRequest(operation=Operation.TRAIN),
        OperationResult.model_validate(trained),
    )
    artifact = train_dir / "output/model"
    model = {"path": str(artifact), "format": FORMAT, "sha256": asset_digest(artifact)}
    test_dir = tmp_path / "evaluate"
    evaluated = execute(
        {"operation": "evaluate", "inputs": {"model": model}, "parameters": {}},
        test_dir,
        lambda _: None,
    )
    report = evaluated["data"]["report"]
    assert len(report["votingOptions"]) == 10, report["members"]
    assert all(member["status"] == "completed" for member in report["members"])
    assert report["recommended"] == [row["algorithm"] for row in report["members"][:3]]
    predictions = read_json(test_dir / "output/report/predictions.json")
    test = predictions["splits"]["test"]
    for option in report["votingOptions"]:
        request = {
            "operation": "predict",
            "inputs": {"model": model},
            "parameters": {"company_ids": test["ids"], "voters": option["members"]},
        }
        predicted = execute(request, tmp_path / "predict", lambda _: None)
        validate_result(
            runtime_spec(),
            OperationRequest(operation=Operation.PREDICT),
            OperationResult.model_validate(predicted),
        )
        ResponsePredict.model_validate(predicted["data"])
        rows = predicted["data"]["items"]
        assert [row["companyId"] for row in rows] == test["ids"]
        thresholds = {row["algorithm"]: row["threshold"] for row in report["members"]}
        votes = sum(
            np.asarray(predictions["scores"][name]["test"]) >= thresholds[name]
            for name in option["members"]
        )
        np.testing.assert_allclose([row["probability"] for row in rows], votes / 3)
        assert all(row["scoreKind"] == "vote_share" for row in rows)
        for index, (row, count) in enumerate(zip(rows, votes, strict=True)):
            detail = row["voting"]
            assert detail["positiveVotes"] == count and detail["requiredVotes"] == 2
            assert row["predictedLabel"] == int(count >= 2)
            assert [member["algorithm"] for member in detail["members"]] == option["members"]
            for member in detail["members"]:
                name = member["algorithm"]
                np.testing.assert_allclose(
                    member["score"],
                    predictions["scores"][name]["test"][index],
                )
                assert member["threshold"] == thresholds[name]
                assert member["vote"] == int(member["score"] >= member["threshold"])
        assert (
            classification_metrics(
                np.asarray(test["labels"]),
                [row["predictedLabel"] for row in rows],
            )
            == option["test"]
        )
    for members in [algorithms[:3], algorithms[2:]]:
        payload = {
            "operation": "predict", "inputs": {"model": model},
            "parameters": {"company_ids": [test["ids"][0]], "voters": members},
        }
        baseline = execute(payload, tmp_path / "predict", lambda _: None)["data"]["items"][0]
        payload["parameters"]["explain"] = True
        data = execute(payload, tmp_path / "explain", lambda _: None)["data"]
        ResponsePredict.model_validate(data)
        row = data["items"][0]
        assert {key: row[key] for key in baseline} == baseline
        sensitivity = row["votingExplanation"]
        assert sensitivity["referenceCount"] == trained["data"]["profile"]["actualCounts"]["train"]
        changes = dict.fromkeys(members, False)
        for feature in sensitivity["features"]:
            assert [member["algorithm"] for member in feature["members"]] == members
            votes = 0
            for before, after in zip(row["voting"]["members"], feature["members"], strict=True):
                assert after["delta"] == pytest.approx(before["score"] - after["scoreAtReference"])
                passed = after["scoreAtReference"] >= before["threshold"]
                assert after["voteAtReference"] == int(passed)
                votes += after["voteAtReference"]
                changes[before["algorithm"]] |= abs(after["delta"]) > 1e-8
            assert feature["positiveVotesAtReference"] == votes
            assert feature["predictedLabelAtReference"] == int(votes >= 2)
        assert len(sensitivity["features"]) >= 1
        assert any(changes.values()), changes
        assert asset_digest(artifact) == model["sha256"]


def test_graph_to_state_uses_training_reference_and_only_visible_neighbors():
    attributes = np.array([[1], [2], [3], [4]], dtype=np.float32)
    meta = {"companyCount": 4, "features": ["amount"], "hyperedgeTypes": ["group"]}
    context = {
        "features": attributes,
        "splits": np.array(["train", "train", "val", "test"]),
        "snapshots": np.array(["train", "train", "valid", "test"]),
        "edges": np.array([[0, 1, 0], [0, 0, 0], [0, 3, 0]]),
        "hyper_nodes_0": np.array([0, 1]),
        "hyper_groups_0": np.array([0, 0]),
    }
    features, view = transform(context, meta)
    assert view["percentileFeatures"] == ["amount"]
    # One outgoing peer, no incoming peer and one same-snapshot group peer.
    np.testing.assert_allclose(
        features[0],
        [1, np.log(2), 0, 0.5, 0, 0, 0, np.log(2), np.log(2), 0.5],
    )
    changed, _ = transform({**context, "features": np.array([[1], [2], [0], [-4]])}, meta)
    np.testing.assert_array_equal(changed[:2], features[:2])
