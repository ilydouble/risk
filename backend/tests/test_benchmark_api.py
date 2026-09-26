import json
import shutil
from dataclasses import replace

import pytest
from com_risk_runtime.artifacts import build_manifest
from fastapi.testclient import TestClient

from risk_api.app import create_app
from risk_api.modules.benchmark import service
from risk_api.modules.benchmark.api import handler

ORIGIN = {"Origin": "http://localhost:18080"}
BASE = "/api/v1/benchmark/"


async def authorize(*_args: object) -> dict[str, str]:
    return {"user_id": "test"}


@pytest.mark.model_integration
def test_benchmark_api_contract(monkeypatch, real_model) -> None:
    monkeypatch.setattr(handler, "authorize_request", authorize)
    with TestClient(create_app()) as client:

        def post(path: str, body: dict) -> dict:
            response = client.post(BASE + path, json=body, headers=ORIGIN)
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload["code"] == 200 and payload["internal_code"] == "SUCCESS"
            return payload["data"]

        listing = post("search", {"pagination": {"page": 1, "pageSize": 2}})
        assert listing["total"] == 474 and len(listing["items"]) == 2
        assert listing["page"] == 1 and listing["pageSize"] == 2
        detail = post("get", {"id": "C00010"})
        assert abs(detail["riskProbability"] - 0.7268730401992798) < 1e-6
        assert detail["observedLabel"] in (0, 1)
        prediction = post("predict", {"companyIds": ["C00010", "C00010"]})
        assert [row["id"] for row in prediction["predictions"]] == ["C00010", "C00010"]
        assert prediction["predictions"][0]["riskProbability"] == detail["riskProbability"]
        graph = post("graph", {"id": "C00010", "limit": 1})
        assert graph["totalEdges"] == 16 and graph["truncated"] is True
        assert len(graph["edges"]) == 1
        explanation = post("explain", {"id": "C00010"})
        assert explanation["method"] == "feature_occlusion_to_training_mean"
        assert explanation["riskProbability"] == detail["riskProbability"]
        assert len(explanation["features"]) == 3
        evaluation = post("evaluation", {})
        assert abs(evaluation["metrics"]["test"]["roc_auc"] - 0.793637480738848) < 1e-10
        assert post("model-card", {})["companyCount"] == 474

        missing = client.post(BASE + "get", json={"id": "missing"}, headers=ORIGIN)
        assert missing.status_code == 404
        assert missing.json()["internal_code"] == "BENCHMARK_COMPANY_NOT_FOUND"
        invalid = client.post(BASE + "predict", json={"companyIds": []}, headers=ORIGIN)
        assert invalid.status_code == 422 and invalid.json()["internal_code"] == "REQUEST_INVALID"
        foreign = client.post(
            BASE + "evaluation", json={}, headers={"Origin": "https://evil.example"}
        )
        assert foreign.status_code == 403


def assert_model_unavailable(monkeypatch, model, data=None) -> None:
    monkeypatch.setattr(handler, "authorize_request", authorize)
    monkeypatch.setattr(
        service,
        "settings",
        replace(
            service.settings,
            benchmark_model_dir=str(model),
            benchmark_data_path=str(data or service.settings.benchmark_data_path),
        ),
    )
    with TestClient(create_app()) as client:
        assert client.get("/health/live").status_code == 200
        assert client.post("/api/v1/auth/register", json={}, headers=ORIGIN).status_code == 422
        response = client.post(BASE + "evaluation", json={}, headers=ORIGIN)
        assert response.status_code == 503
        assert response.json()["internal_code"] == "BENCHMARK_MODEL_UNAVAILABLE"
        assert response.json()["code"] == 503 and response.headers["X-Request-ID"]


def test_missing_model_only_disables_benchmark(monkeypatch, tmp_path) -> None:
    assert_model_unavailable(monkeypatch, tmp_path)


@pytest.mark.model_integration
@pytest.mark.parametrize(
    "failure", ["missing", "modified", "snapshot", "manifest", "runtime", "metadata", "path"]
)
def test_invalid_bundle_only_disables_benchmark(monkeypatch, real_model, tmp_path, failure):
    source_model, source_data = real_model
    model = tmp_path / "model"
    data = tmp_path / "snapshot.json"
    shutil.copytree(source_model, model)
    shutil.copyfile(source_data, data)
    manifest_path = model / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if failure == "missing":
        (model / "weights.pt").unlink()
    elif failure == "modified":
        with (model / "weights.pt").open("ab") as stream:
            stream.write(b"modified")
    elif failure == "snapshot":
        data.write_text(data.read_text() + "\n")
    elif failure == "metadata":
        metadata_path = model / "metadata.json"
        metadata = json.loads(metadata_path.read_text())
        metadata["version"] = 999
        metadata_path.write_text(json.dumps(metadata))
        manifest_path.write_text(build_manifest(model, "smesd-v1", data).model_dump_json())
    else:
        if failure == "manifest":
            manifest["manifest_version"] = 999
        elif failure == "runtime":
            manifest["runtime_api_version"] = 999
        else:
            manifest["files"][0]["path"] = "../weights.pt"
        manifest_path.write_text(json.dumps(manifest))
    assert_model_unavailable(monkeypatch, model, data)
