import asyncio

import httpx
import pytest

from risk_api.errors import AppError
from risk_api.modules.modeling.client import ModelClient
from risk_api.shared.logging import request_log_context


def test_internal_envelope_mapping_and_request_correlation():
    async def exercise():
        def success(request):
            assert request.headers["X-Request-ID"] == "gateway-id"
            return httpx.Response(200, json={"code": 200, "data": {"status": "queued"}})

        async with httpx.AsyncClient(
            base_url="http://model", transport=httpx.MockTransport(success)
        ) as http:
            with request_log_context("gateway-id"):
                assert await ModelClient(http).call("jobs/get", {}) == {"status": "queued"}
        for response, expected in [
            (httpx.Response(503, text="unavailable"), "MODEL_SERVICE_UNAVAILABLE"),
            (httpx.Response(200, json={"code": 201, "data": {}}), "MODEL_SERVICE_UNAVAILABLE"),
            (
                httpx.Response(
                    404, json={"code": 404, "internal_code": "MODEL_RESOURCE_NOT_FOUND"}
                ),
                "MODEL_RESOURCE_NOT_FOUND",
            ),
        ]:
            async with httpx.AsyncClient(
                base_url="http://model",
                transport=httpx.MockTransport(lambda _, response=response: response),
            ) as http:
                with pytest.raises(AppError) as error:
                    await ModelClient(http).call("jobs/get", {})
                assert error.value.code == expected

    asyncio.run(exercise())
