from fastapi.testclient import TestClient
from service.api.app import create_app


def test_service_auth_validation_envelope_and_schema(monkeypatch):
    monkeypatch.setenv("RISK_GNN_API_TOKEN", "contract-test-token")
    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        denied = client.post(
            "/internal/v1/jobs/get", json={}, headers={"X-Request-ID": "gateway-selected"}
        )
        assert denied.status_code == 401
        assert denied.headers["X-Request-ID"] == "gateway-selected"
        assert denied.json()["internal_code"] == "SERVICE_UNAUTHORIZED"
        invalid = client.post(
            "/internal/v1/models/predict",
            json={"companyIds": ["a"] * 33},
            headers={"Authorization": "Bearer contract-test-token"},
        )
        assert invalid.status_code == 422 and invalid.json()["code"] == 422
        assert invalid.headers["X-Request-ID"]
        catalog = client.post(
            "/internal/v1/models/capabilities",
            json={},
            headers={"Authorization": "Bearer contract-test-token"},
        )
        assert catalog.status_code == 200
        models = {item["id"]: item for item in catalog.json()["data"]["items"]}
        assert models["riskgnn-node-only"]["trainable"] is True
        assert models["riskgnn-plus"]["trainable"] is False
        assert client.get("/health/live").status_code == 200
        assert client.get("/unknown").json()["code"] == 404
    for path, operations in app.openapi()["paths"].items():
        assert path.startswith("/internal/v1/")
        assert {"200", "401", "404", "409", "422", "503"} <= operations["post"]["responses"].keys()
