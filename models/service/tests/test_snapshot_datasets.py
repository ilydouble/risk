import json
from zipfile import ZipFile

import numpy as np
import pytest

from riskgnn.dataset_adapters.packaging import package
from riskgnn.dataset_adapters.registry import inspect, resolve
from riskgnn.dataset_adapters.smesd.schemas import check as check_smesd
from riskgnn.dataset_adapters.snapshot_io import load
from riskgnn.dataset_adapters.snapshot_schema import Snapshot
from riskgnn.dataset_adapters.uk_dataset_v1.schemas import check as check_uk
from riskgnn.workbench.artifacts import read_json
from riskgnn.workbench.sampling import Sampler


@pytest.fixture(
    params=[("smesd", "comrisk_export_v5/smesd", 3976), ("uk-dataset-v1", "uk_dataset_v1", 233251)]
)
def snapshot_zip(request, datasets, tmp_path):
    adapter, folder, count = request.param
    source = datasets / folder
    archive = tmp_path / "snapshot.zip"
    package(
        source,
        archive,
        "smesd" if adapter == "smesd" else "uk-companies-legacy",
        "real-local",
        overrides={"target_count": 60},
    )
    return archive, count


def test_real_snapshots_keep_semantics_and_train_only_preprocessing(snapshot_zip, tmp_path):
    source, count = snapshot_zip
    result = inspect(source, tmp_path / "validated")
    assert result["counts"]["company_attr"] == count
    assert result["supportedRunnerIds"] == ["riskgnn"]
    assert result["analysis"]["totalRows"] == count
    adapter, contract = resolve(source)
    meta = adapter.prepare(
        tmp_path / "validated", tmp_path / "prepared", contract["adapter"]["config"]
    )
    context = dict(np.load(tmp_path / "prepared/context.npz", allow_pickle=False))
    assert meta["targetCount"] == 60
    assert meta["evaluation"] == "isolated_snapshots"
    assert meta["preprocessing"]["fitSplit"] == "train"
    assert set(meta["retainedOnlyInputs"]) >= {"hyperedges", "events"}
    edges = context["edges"]
    assert np.all(context["snapshots"][edges[:, 0]] == context["snapshots"][edges[:, 1]])
    assert np.all(context["labels"][meta["companyCount"] :] == -1)
    np.testing.assert_allclose(
        context["features"][context["splits"] == "train"].mean(axis=0), 0, atol=2e-6
    )
    evidence = read_json(tmp_path / "prepared/evidence.json")
    assert any(s["hyperedges"] for s in evidence.values())
    if adapter.id == "smesd":
        assert meta["personCount"] > 0
        assert any(s["events"] for s in evidence.values())
    else:
        assert len(meta["features"]) == 7
        assert meta["personCount"] == 0
        assert not np.all(context["weights"] == 1)
    # CSR sampling must preserve direction and use each original edge's weight/confidence.
    sampler = Sampler(edges, len(context["labels"]), context["weights"], context["confidence"])
    nodes, selected, types, weights, confidence = sampler.sample_graph(
        np.where(context["splits"] == "train")[0].tolist(), 10
    )
    lookup = {tuple(edge): i for i, edge in enumerate(edges)}
    for (a, b), relation, weight, q in zip(selected, types, weights, confidence, strict=True):
        i = lookup[(int(nodes[a]), int(nodes[b]), int(relation))]
        assert float(weight) == float(context["weights"][i])
        assert float(q) == float(context["confidence"][i])


def test_v5_person_company_schema_and_uk_fields_are_not_inferred(datasets):
    smesd = load(datasets / "comrisk_export_v5/smesd")
    check_smesd(smesd)
    snapshot = smesd["train"].model_dump()
    person = next(n for n in snapshot["nodes"] if n["kind"] == "person")
    person["label"] = 1
    with pytest.raises(ValueError, match="Persons"):
        Snapshot.model_validate(snapshot)
    uk = load(datasets / "uk_dataset_v1")
    check_uk(uk)
    uk["train"].hyperedge_types = uk["train"].hyperedge_types[:2]
    with pytest.raises(ValueError, match="three-hyperedge"):
        check_uk(uk)


def test_uk_file_hash_must_match_delivered_audit(datasets, tmp_path):
    source = datasets / "uk_dataset_v1"
    raw = tmp_path / "raw"
    raw.mkdir()
    for name in ("train.json", "valid.json", "test.json", "audit.json", "export_meta.json"):
        if name == "audit.json":
            audit = json.loads((source / name).read_text())
            audit["snapshots"]["train"]["sha256"] = "0" * 64
            (raw / name).write_text(json.dumps(audit))
        else:
            (raw / name).write_bytes((source / name).read_bytes())
    wrapped = tmp_path / "wrapped.zip"
    package(raw, wrapped, "uk-companies-legacy", "v1")
    with pytest.raises(ValueError, match="SHA-256"):
        inspect(wrapped, tmp_path / "validated")


def test_retired_bundle_and_raw_pickle_are_not_upload_protocols(tmp_path, datasets):
    archive = tmp_path / "old.zip"
    with ZipFile(archive, "w") as zipped:
        zipped.writestr(
            "risk_dataset_contract.json",
            json.dumps(
                {
                    "contract_version": 1,
                    "dataset": {"id": "old", "version": "1"},
                    "adapter": {"id": "bundle", "version": "1", "config": {}},
                }
            ),
        )
    with pytest.raises(ValueError, match="not supported"):
        resolve(archive)
    with pytest.raises(ValueError, match="Missing required files"):
        package(datasets / "smesd", tmp_path / "raw-pickle.zip", "smesd", "raw")
