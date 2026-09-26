import json
import shutil
import tarfile

import pytest
from com_risk_runtime.artifacts import build_manifest, validate_bundle
from com_risk_runtime.explain import explain
from com_risk_runtime.predictor import Predictor

from training.export import export_bundle


@pytest.fixture(scope="module")
def exported(trained, tmp_path_factory):
    run, dataset, _ = trained
    root = tmp_path_factory.mktemp("exported")
    snapshot = root / "snapshot.json"
    dataset.write(snapshot)
    archive = export_bundle(run, "synthetic-v1", snapshot, root / "exports")
    return root, snapshot, archive


def test_export_portable_prediction_and_explanation(exported, trained, tmp_path):
    root, snapshot, archive = exported
    run, dataset, report = trained
    with tarfile.open(archive) as stream:
        assert set(stream.getnames()) == {
            "synthetic-v1",
            *[
                f"synthetic-v1/{name}"
                for name in ("weights.pt", "metadata.json", "metrics.json", "manifest.json")
            ],
        }
        stream.extractall(tmp_path, filter="data")
    independent_snapshot = tmp_path / "separate-data.json"
    shutil.copyfile(snapshot, independent_snapshot)
    package = tmp_path / "synthetic-v1"
    bundle = validate_bundle(package, independent_snapshot, expected_version="synthetic-v1")
    ids = [dataset.nodes[1].id, dataset.nodes[0].id, dataset.nodes[1].id]
    predictor = Predictor(package)
    assert predictor.predict(bundle.dataset, ids) == Predictor(run).predict(dataset, ids)
    assert explain(predictor, bundle.dataset, ids[0]) == explain(Predictor(run), dataset, ids[0])
    assert bundle.metrics == report
    for name in ("weights.pt", "metadata.json", "metrics.json"):
        assert (package / name).read_bytes() == (run / name).read_bytes()
    with pytest.raises(FileExistsError):
        export_bundle(run, "synthetic-v1", snapshot, root / "exports")


@pytest.mark.parametrize(
    "change",
    [
        "empty",
        "missing",
        "modified",
        "snapshot",
        "metadata",
        "manifest_version",
        "runtime_api_version",
        "duplicate",
        "version",
        "snapshot_identity",
        "training_snapshot",
    ],
)
def test_invalid_bundle_is_rejected(exported, tmp_path, change):
    root, source_snapshot, _ = exported
    package = tmp_path / "package"
    shutil.copytree(root / "exports/synthetic-v1", package)
    snapshot = tmp_path / "test.json"
    shutil.copyfile(source_snapshot, snapshot)
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    match change:
        case "empty":
            shutil.rmtree(package)
            package.mkdir()
        case "missing":
            (package / "weights.pt").unlink()
        case "modified":
            with (package / "weights.pt").open("ab") as stream:
                stream.write(b"modified")
        case "snapshot":
            snapshot.write_text(snapshot.read_text() + "\n")
        case "metadata":
            path = package / "metadata.json"
            metadata = json.loads(path.read_text())
            metadata["version"] = 999
            path.write_text(json.dumps(metadata))
            manifest_path.write_text(
                build_manifest(package, "synthetic-v1", snapshot).model_dump_json()
            )
        case "manifest_version" | "runtime_api_version":
            manifest[change] = 999
            manifest_path.write_text(json.dumps(manifest))
        case "duplicate":
            manifest["files"].append(manifest["files"][0])
            manifest_path.write_text(json.dumps(manifest))
        case "version":
            manifest["model_version"] = "wrong-version"
            manifest_path.write_text(json.dumps(manifest))
        case "snapshot_identity":
            manifest["snapshot"]["company_count"] += 1
            manifest_path.write_text(json.dumps(manifest))
        case "training_snapshot":
            data = json.loads(snapshot.read_text())
            data["nodes"][0]["features"][0] += 1
            snapshot.write_text(json.dumps(data))
            manifest_path.write_text(
                build_manifest(package, "synthetic-v1", snapshot).model_dump_json()
            )
    with pytest.raises((ValueError, FileNotFoundError)):
        validate_bundle(package, snapshot, expected_version="synthetic-v1")


@pytest.mark.parametrize(
    "path",
    [
        "../weights.pt",
        "/weights.pt",
        "x/../weights.pt",
        "./weights.pt",
        "C:\\weights.pt",
        "x\\weights.pt",
        "extra.pt",
    ],
)
def test_manifest_paths_cannot_escape_package(exported, tmp_path, path):
    root, snapshot, _ = exported
    shutil.copytree(root / "exports/synthetic-v1", tmp_path / "package")
    package = tmp_path / "package"
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"][0]["path"] = path
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="manifest path"):
        validate_bundle(package, snapshot)


def test_external_symlink_is_rejected(exported, tmp_path):
    root, snapshot, _ = exported
    package = tmp_path / "package"
    shutil.copytree(root / "exports/synthetic-v1", package)
    weights = package / "weights.pt"
    weights.rename(tmp_path / "external.pt")
    weights.symlink_to(tmp_path / "external.pt")
    with pytest.raises(ValueError, match="escapes model directory"):
        validate_bundle(package, snapshot)


def test_export_rejects_invalid_version_before_writing(trained, tmp_path):
    run, dataset, _ = trained
    snapshot = tmp_path / "snapshot.json"
    dataset.write(snapshot)
    with pytest.raises(ValueError, match="directory name"):
        export_bundle(run, "../escape", snapshot, tmp_path / "exports")
    assert not (tmp_path / "exports").exists()
