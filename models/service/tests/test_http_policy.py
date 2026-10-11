import asyncio
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from model_service.app import create_app
from model_service.modules.jobs.model import Base


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
        assert models["riskgnn"]["trainable"] is True
        assert models["riskgnn"]["datasetFormats"] == [
            "sg-comrisk-v1",
            "smesd-json-v5",
            "uk-dataset-v1",
        ]
        assert list(models) == ["riskgnn"]
        adapters = client.post(
            "/internal/v1/models/runtime",
            json={},
            headers={"Authorization": "Bearer contract-test-token"},
        ).json()["data"]["runtime"]
        assert adapters["runtime_version"] == "2"
        assert set(adapters["operations"]) == {"inspect", "train", "evaluate", "predict"}
        assert (
            adapters["operations"]["train"]["parameters_schema"]["properties"]["epochs"]["maximum"]
            == 20
        )
        assert client.get("/health/live").status_code == 200
        assert client.get("/unknown").json()["code"] == 404
    for path, operations in app.openapi()["paths"].items():
        assert path.startswith("/internal/v1/")
        assert {"200", "401", "404", "409", "422", "503"} <= operations["post"]["responses"].keys()


def test_job_artifact_and_prediction_routes_share_dishka_store(monkeypatch):
    url = os.getenv("RISK_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set RISK_TEST_DATABASE_URL for the HTTP module integration contract")
    schema = "test_http_" + uuid4().hex

    async def prepare():
        engine = create_async_engine(url)
        try:
            async with engine.begin() as connection:
                await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                await connection.run_sync(Base.metadata.create_all)
        finally:
            await engine.dispose()

    async def cleanup():
        engine = create_async_engine(url)
        try:
            async with engine.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        finally:
            await engine.dispose()

    # The production Provider owns the engine; only its connection is scoped to test tables.
    monkeypatch.setattr(
        "model_service.dependencies.create_engine",
        lambda settings: create_async_engine(
            url, connect_args={"server_settings": {"search_path": schema}}
        ),
    )
    monkeypatch.setenv("RISK_GNN_API_TOKEN", "http-contract-token")
    asyncio.run(prepare())
    try:
        with TestClient(create_app(), raise_server_exceptions=False) as client:
            headers = {
                "Authorization": "Bearer http-contract-token",
                "X-Request-ID": "http-module-contract",
            }

            def post(path, body, expected=200):
                response = client.post("/internal/v1/" + path, json=body, headers=headers)
                assert response.status_code == expected, response.text
                assert response.headers["X-Request-ID"] == headers["X-Request-ID"]
                assert response.json()["code"] == expected
                return response.json()

            generic = {
                "jobId": str(uuid4()),
                "kind": "execute",
                "payload": {
                    "runtime_id": "riskgnn",
                    "runtime_version": "2",
                    "operation": "inspect",
                    "inputs": {
                        "dataset": {
                            "object_key": "uploads/source/data.zip",
                            "sha256": "a" * 64,
                            "format": "zip",
                        }
                    },
                    "parameters": {},
                },
            }
            accepted = post("jobs/submit", generic)["data"]
            assert accepted["kind"] == "execute" and accepted["status"] == "queued"
            assert post("jobs/submit", generic)["data"] == accepted
            unsupported = {
                **generic,
                "jobId": str(uuid4()),
                "payload": {**generic["payload"], "runtime_version": "absent"},
            }
            assert (
                post("jobs/submit", unsupported, 422)["internal_code"]
                == "MODEL_RUNTIME_INCOMPATIBLE"
            )
            post("jobs/cancel", {"jobId": generic["jobId"]})
            identity = str(uuid4())
            body = {
                "jobId": identity,
                "kind": "validate",
                "payload": {"objectKey": f"uploads/{uuid4()}/{uuid4()}.zip"},
            }
            job = post("jobs/submit", body)["data"]
            assert job["id"] == identity and job["status"] == "queued"
            assert post("jobs/submit", body)["data"] == job
            assert post("jobs/get", {"jobId": identity})["data"] == job
            assert post("artifacts/get", {"jobId": identity})["data"] == job
            assert isinstance(post("jobs/events", {"jobId": identity})["data"]["items"], list)
            assert post("jobs/cancel", {"jobId": identity})["data"]["status"] == "cancelled"
            conflict = post(
                "jobs/submit",
                {**body, "payload": {"objectKey": f"uploads/{uuid4()}/{uuid4()}.zip"}},
                409,
            )
            assert conflict["internal_code"] == "MODEL_STATE_INVALID"
            assert post("jobs/get", {"jobId": str(uuid4())}, 404)["internal_code"] == (
                "MODEL_RESOURCE_NOT_FOUND"
            )
            assert (
                post("models/predict", {"jobId": identity, "companyIds": ["company"]}, 409)[
                    "internal_code"
                ]
                == "MODEL_STATE_INVALID"
            )
    finally:
        asyncio.run(cleanup())
