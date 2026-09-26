import json
import logging
from io import StringIO
from uuid import UUID

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from httpx import Response

from risk_api.app import create_app
from risk_api.errors import AppError, register_error_handlers
from risk_api.shared.api.middleware import request_policy
from risk_api.shared.logging import configure_logging, request_log_context


def _events(stream: StringIO, message: str) -> list[dict[str, object]]:
    return [
        event
        for line in stream.getvalue().splitlines()
        if (event := json.loads(line))["msg"] == message
    ]


def _request_id(response: Response, incoming: str | None) -> str:
    values = response.headers.get_list("X-Request-ID")
    assert len(values) == 1
    if incoming:
        assert values[0] == incoming
    else:
        assert UUID(values[0]).version == 4
    return values[0]


@pytest.mark.parametrize("incoming", [None, "", "log-request"])
def test_request_logs_correlate_success_and_rejected_requests(incoming: str | None) -> None:
    stream = StringIO()
    headers = {} if incoming is None else {"X-Request-ID": incoming}
    with TestClient(create_app(), raise_server_exceptions=False) as client:
        configure_logging(output_format="json", stream=stream)
        configure_logging(output_format="json", stream=stream)
        successful = client.get("/openapi.json", headers=headers)
        rejected = client.post(
            "/api/v1/auth/login",
            json={"password": "top-secret"},
            headers={**headers, "Origin": "http://evil.example"},
        )
        invalid = client.post(
            "/api/v1/auth/login",
            json={"password": "top-secret"},
            headers={**headers, "Origin": "http://localhost:18080"},
        )
        client.get("/health/live")

    assert (successful.status_code, rejected.status_code, invalid.status_code) == (200, 403, 422)
    request_ids = [_request_id(response, incoming) for response in (successful, rejected, invalid)]
    if not incoming:
        assert len(set(request_ids)) == 3
    events = _events(stream, "http.request_completed")
    assert [(event["request_id"], event["status"], event["internal_code"]) for event in events] == [
        (request_ids[0], 200, "SUCCESS"),
        (request_ids[1], 403, "REQUEST_ORIGIN_INVALID"),
        (request_ids[2], 422, "REQUEST_INVALID"),
    ]
    assert all(event["service"] == "risk-backend" for event in events)
    assert [event["route"] for event in events] == [
        "<unmatched>",
        "<unmatched>",
        "/api/v1/auth/login",
    ]
    assert "top-secret" not in stream.getvalue()


def test_request_log_uses_dynamic_route_template() -> None:
    test_app = FastAPI()
    test_app.middleware("http")(request_policy)
    router = APIRouter()

    @router.get("/items/{item_id}")
    async def get_item(item_id: str) -> dict[str, str]:
        return {"id": item_id}

    test_app.include_router(router, prefix="/api/v1")
    stream = StringIO()
    configure_logging(output_format="json", stream=stream)
    with TestClient(test_app) as client:
        response = client.get("/api/v1/items/private-123", headers={"X-Request-ID": "log-dynamic"})

    assert response.status_code == 200
    assert _events(stream, "http.request_completed")[0]["route"] == "/api/v1/items/{item_id}"
    assert "private-123" not in stream.getvalue()


@pytest.mark.parametrize("incoming", [None, "", "log-failure"])
def test_unhandled_error_logs_stack_and_request_id(incoming: str | None) -> None:
    test_app = FastAPI()
    register_error_handlers(test_app)
    test_app.middleware("http")(request_policy)

    @test_app.get("/crash")
    async def crash() -> None:
        raise RuntimeError("test failure")

    stream = StringIO()
    configure_logging(output_format="json", stream=stream)
    with TestClient(test_app, raise_server_exceptions=False) as client:
        headers = {} if incoming is None else {"X-Request-ID": incoming}
        response = client.get("/crash", headers=headers)

    assert response.status_code == 500
    assert response.json()["internal_code"] == "INTERNAL_ERROR"
    completion = _events(stream, "http.request_completed")
    failure = _events(stream, "http.unhandled_error")
    assert len(completion) == len(failure) == 1
    assert (
        completion[0]["request_id"] == failure[0]["request_id"] == _request_id(response, incoming)
    )
    assert completion[0]["status"] == 500
    assert failure[0]["exception"]["type"] == "RuntimeError"  # type: ignore[index]


@pytest.mark.parametrize("incoming", [None, "", "log-unavailable"])
def test_handled_server_error_logs_stable_code_without_cause_message(incoming: str | None) -> None:
    test_app = FastAPI()
    register_error_handlers(test_app)
    test_app.middleware("http")(request_policy)

    @test_app.get("/unavailable")
    async def unavailable() -> None:
        try:
            raise OSError("internal connection detail")
        except OSError as error:
            raise AppError(503, "STORE_UNAVAILABLE", "Store unavailable") from error

    stream = StringIO()
    configure_logging(output_format="json", stream=stream)
    with TestClient(test_app, raise_server_exceptions=False) as client:
        headers = {} if incoming is None else {"X-Request-ID": incoming}
        response = client.get("/unavailable", headers=headers)

    assert response.status_code == 503
    handled = _events(stream, "http.handled_error")
    completion = _events(stream, "http.request_completed")
    assert len(handled) == len(completion) == 1
    assert (
        handled[0]["request_id"] == completion[0]["request_id"] == _request_id(response, incoming)
    )
    assert handled[0]["internal_code"] == completion[0]["internal_code"] == "STORE_UNAVAILABLE"
    assert handled[0]["cause_type"] == "OSError"
    assert "internal connection detail" not in stream.getvalue()


def test_pretty_format_keeps_correlation_and_redaction() -> None:
    stream = StringIO()
    configure_logging(output_format="pretty", stream=stream)
    with request_log_context("pretty-request"):
        logging.getLogger("risk_api.test").info(
            "test.pretty", extra={"password": "hidden-secret"}
        )

    output = stream.getvalue()
    assert "test.pretty" in output
    assert 'request_id="pretty-request"' in output
    assert 'password="[REDACTED]"' in output
    assert "hidden-secret" not in output
