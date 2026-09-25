from fastapi.testclient import TestClient

from risk_api.main import app
from risk_api.modules.company.api.schemas import ResponseSearchCompany


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
        schema["components"]["schemas"][login_schema_name]["properties"]["internal_code"]["const"]
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


def test_search_pagination_contract() -> None:
    schemas = app.openapi()["components"]["schemas"]
    request = schemas["RequestSearchCompany"]["properties"]
    response = schemas["ResponseSearchCompany"]["properties"]
    assert "page" not in request and "pageSize" not in request
    assert request["pagination"]["$ref"] == "#/components/schemas/PageRequest"
    assert "pagination" not in response
    assert "page" in response and "pageSize" in response
    assert ResponseSearchCompany(items=[], total=0, page=2, pageSize=25).model_dump() == {
        "items": [],
        "total": 0,
        "page": 2,
        "pageSize": 25,
    }

    with TestClient(app, raise_server_exceptions=False) as client:
        invalid = client.post(
            "/api/v1/company/search",
            json={"page": 2, "pageSize": 25},
            headers={"Origin": "http://localhost:18080"},
        )
        assert invalid.status_code == 422
        assert invalid.json()["internal_code"] == "REQUEST_INVALID"
