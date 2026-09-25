from fastapi.testclient import TestClient

from risk_api.app import create_app
from risk_api.modules.company.api.schemas import ResponseSearchCompany


def test_create_app_owns_separate_containers() -> None:
    first = create_app()
    second = create_app()
    assert first.state.dishka_container is not second.state.dishka_container

    with TestClient(first) as first_client, TestClient(second) as second_client:
        assert first_client.get("/health/live").json() == {"status": "ok"}
        assert second_client.get("/health/live").json() == {"status": "ok"}


def test_error_envelope_and_openapi_contract() -> None:
    app = create_app()
    schema = app.openapi()
    routes = schema["paths"]
    for path in (
        "/api/v1/auth/register",
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
    register_409 = routes["/api/v1/auth/register"]["post"]["responses"]["409"]
    register_schema_name = register_409["content"]["application/json"]["schema"]["$ref"].split("/")[
        -1
    ]
    assert (
        schema["components"]["schemas"][register_schema_name]["properties"]["internal_code"][
            "const"
        ]
        == "AUTH_USERNAME_TAKEN"
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

        invalid_registration = client.post(
            "/api/v1/auth/register",
            json={"username": "bad space", "displayName": "Test", "password": "short"},
            headers={"Origin": "http://localhost:18080"},
        )
        assert invalid_registration.status_code == 422
        assert invalid_registration.json()["internal_code"] == "REQUEST_INVALID"

        rejected = client.post(
            "/api/v1/auth/login", json={}, headers={"Origin": "http://evil.example"}
        )
        assert rejected.status_code == 403
        assert rejected.json()["internal_code"] == "REQUEST_ORIGIN_INVALID"

        missing = client.get("/unknown")
        assert missing.status_code == 404
        assert missing.json()["internal_code"] == "ROUTE_NOT_FOUND"


def test_search_pagination_contract() -> None:
    app = create_app()
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
