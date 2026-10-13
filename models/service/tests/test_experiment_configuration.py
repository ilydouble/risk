from copy import deepcopy

import pytest

from model_service.execution.contracts import Operation, OperationRequest
from model_service.execution.invocation import Invocation
from riskgnn.dataset_adapters.packaging import package
from riskgnn.dataset_adapters.registry import inspect, resolve
from riskgnn.workbench import configuration


def dataset_contract(adapter="smesd", config=None):
    return {
        "contract_version": 1,
        "dataset": {"id": "cohort", "version": "v5"},
        "adapter": {"id": adapter, "version": "1", "config": config or {}},
    }


@pytest.mark.parametrize(
    "adapter,default", [("smesd", 4000), ("sg-comrisk", 2000), ("uk-dataset-v1", 2000)]
)
def test_model_defaults_zip_defaults_and_explicit_parameters(adapter, default):
    assert configuration.resolve(dataset_contract(adapter), {})["resolvedParameters"] == {
        "epochs": 2,
        "algorithm": "riskgnn-plus",
        "dataset": {"target_count": default},
    }
    contract = dataset_contract(adapter, {"target_count": 60})
    snapshot = configuration.resolve(contract, {"dataset": {"target_count": 2000}})
    assert snapshot["defaultParameters"]["dataset"]["target_count"] == 60
    assert snapshot["resolvedParameters"] == {
        "epochs": 2,
        "dataset": {"target_count": 2000},
        "algorithm": "riskgnn-plus",
    }
    assert snapshot["requestedParameters"] == {"dataset": {"target_count": 2000}}
    assert contract["adapter"]["config"] == {"target_count": 60}
    assert snapshot["schemaDigest"] == configuration.descriptor_digest(snapshot)


@pytest.mark.parametrize(
    "parameters",
    [
        {"epochs": 0},
        {"epochs": 21},
        {"epochs": True},
        {"epochs": 1.5},
        {"dataset": {"target_count": 5}},
        {"dataset": {"target_count": 20001}},
        {"dataset": {"target_count": True}},
        {"dataset": {"target_count": "60"}},
        {"dataset": None},
        {"dataset": {"seed": 1}},
        {"learning_rate": 0.1},
        {"adapter": {"id": "another"}},
    ],
)
def test_model_rejects_undeclared_parameters_and_invalid_values(parameters):
    with pytest.raises(configuration.ConfigurationError):
        configuration.resolve(dataset_contract(), parameters)


def test_frozen_configuration_survives_default_changes_but_rejects_tampering(monkeypatch):
    contract = dataset_contract(config={"target_count": 60})
    snapshot = configuration.resolve(contract, {"epochs": 1})
    current = configuration.describe(contract)
    current["defaultParameters"] = {"epochs": 4, "dataset": {"target_count": 2000}}
    current["schemaDigest"] = configuration.descriptor_digest(current)
    monkeypatch.setattr(configuration, "describe", lambda _: deepcopy(current))
    assert (
        configuration.validate_frozen(contract, snapshot["resolvedParameters"], snapshot)
        == snapshot
    )
    with pytest.raises(configuration.ConfigurationError, match="changed"):
        configuration.resolve(contract, {}, snapshot["schemaDigest"])
    with pytest.raises(configuration.ConfigurationError, match="differ"):
        configuration.validate_frozen(contract, {"epochs": 4}, snapshot)
    changed = deepcopy(snapshot)
    changed["defaultParameters"]["epochs"] = 10
    with pytest.raises(configuration.ConfigurationError, match="checksum"):
        configuration.validate_frozen(contract, snapshot["resolvedParameters"], changed)
    current["parameterSchema"]["properties"]["epochs"]["minimum"] = 2
    with pytest.raises(configuration.ConfigurationError):
        configuration.validate_frozen(contract, snapshot["resolvedParameters"], snapshot)


def test_dataset_parameters_are_bound_to_the_completion_receipt(tmp_path):
    snapshots = [
        configuration.resolve(
            dataset_contract(),
            {
                "epochs": 1,
                "dataset": {"target_count": count},
            },
        )
        for count in (60, 2000)
    ]
    calls = [
        Invocation(
            runtime_id="riskgnn",
            runtime_version="3",
            run_id="same-run",
            attempt_id="1",
            request_id="id",
            directory=tmp_path,
            request=OperationRequest(
                operation=Operation.TRAIN,
                parameters=snapshot["resolvedParameters"],
                configuration=snapshot,
            ),
        )
        for snapshot in snapshots
    ]
    assert calls[0].binding() != calls[1].binding()


def test_requested_count_can_exceed_available_real_targets(datasets, tmp_path):
    archive = tmp_path / "smesd.zip"
    package(datasets / "comrisk_export_v5/smesd", archive, "smesd", "v5")
    validated = tmp_path / "validated"
    inspect(archive, validated)
    adapter, contract = resolve(archive)
    snapshot = configuration.resolve(contract, {"dataset": {"target_count": 4000}})
    prepared = adapter.prepare(
        validated, tmp_path / "prepared", snapshot["resolvedParameters"]["dataset"]
    )
    assert prepared["targetCount"] == 3976
    assert snapshot["resolvedParameters"]["dataset"]["target_count"] == 4000
