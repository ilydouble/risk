from fastapi.testclient import TestClient

from risk_api.main import app


def test_error_envelope_and_openapi_contract() -> None:
    schema = app.openapi()
    routes = schema["paths"]
    for path in (
        "/api/v1/auth/login",
        "/api/v1/auth/logout",
        "/api/v1/auth/me",
        "/api/v1/company/search",
        "/api/v1/company/get",
        "/api/v1/graph/get",
        "/api/v1/score/get",
        "/api/v1/document/create-upload",
        "/api/v1/document/complete-upload",
        "/api/v1/document/list",
        "/api/v1/document/create-download",
    ):
        assert "post" in routes[path]
        assert "422" in routes[path]["post"]["responses"]

    # Module-specific error codes are part of the exported contract, not only runtime JSON.
    login_401 = routes["/api/v1/auth/login"]["post"]["responses"]["401"]
    login_schema_name = login_401["content"]["application/json"]["schema"]["$ref"].split("/")[-1]
    assert (
        schema["components"]["schemas"][login_schema_name]["properties"]["internal_code"][
            "const"
        ]
        == "AUTH_INVALID_CREDENTIALS"
    )
    upload_409 = routes["/api/v1/document/complete-upload"]["post"]["responses"]["409"]
    assert len(upload_409["content"]["application/json"]["schema"]["anyOf"]) == 2

    with TestClient(app, raise_server_exceptions=False) as client:
        invalid = client.post(
            "/api/v1/auth/login", json={}, headers={"Origin": "http://localhost:18080"}
        )
        assert invalid.status_code == 422
        assert invalid.json()["code"] == 422
        assert invalid.json()["internal_code"] == "REQUEST_INVALID"
        assert invalid.headers["X-Request-ID"]

        rejected = client.post(
            "/api/v1/auth/login", json={}, headers={"Origin": "http://evil.example"}
        )
        assert rejected.status_code == 403
        assert rejected.json()["internal_code"] == "REQUEST_ORIGIN_INVALID"

        missing = client.get("/unknown")
        assert missing.status_code == 404
        assert missing.json()["internal_code"] == "ROUTE_NOT_FOUND"
