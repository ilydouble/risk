from fastapi.testclient import TestClient

from risk_api.app import create_app
from risk_api.modules.benchmark.api import handler
from risk_api.modules.benchmark.service import BenchmarkService

ORIGIN = {"Origin": "http://localhost:18080"}
BASE = "/api/v1/benchmark/"


async def authorize(*_args: object) -> dict[str, str]:
    return {"user_id": "test"}


def test_benchmark_api_contract(monkeypatch) -> None:
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


def test_missing_model_only_disables_benchmark(monkeypatch) -> None:
    monkeypatch.setattr(handler, "authorize_request", authorize)

    def fail(_self: BenchmarkService) -> None:
        raise FileNotFoundError("missing weights")

    monkeypatch.setattr(BenchmarkService, "_verify_bundle", fail)
    with TestClient(create_app()) as client:
        assert client.get("/health/live").status_code == 200
        response = client.post(BASE + "evaluation", json={}, headers=ORIGIN)
        assert response.status_code == 503
        assert response.json()["internal_code"] == "BENCHMARK_MODEL_UNAVAILABLE"
