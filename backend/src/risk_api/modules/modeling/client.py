"""Internal HTTP contract adapter; this module never imports the model package."""

from typing import Any

import httpx

from risk_api.errors import AppError
from risk_api.shared.logging import current_request_id


class ModelClient:
    def __init__(self, http: httpx.AsyncClient):
        self.http = http

    async def call(self, action: str, body: dict, request_id: str = "") -> dict[str, Any]:
        request_id = request_id or current_request_id() or ""
        try:
            response = await self.http.post(
                "/internal/v1/" + action,
                json=body,
                headers={"X-Request-ID": request_id} if request_id else {},
                timeout=70 if action == "models/predict" else 10,
            )
            data = response.json()
            if response.status_code >= 500:
                raise AppError(503, "MODEL_SERVICE_UNAVAILABLE", "Model service unavailable")
            if response.status_code >= 400:
                raise AppError(
                    response.status_code,
                    data.get("internal_code", "MODEL_REQUEST_FAILED"),
                    data.get("message", "Model request failed"),
                )
            if data.get("code") != response.status_code or not isinstance(data.get("data"), dict):
                raise ValueError("Invalid model-service envelope")
            return data["data"]
        except (httpx.HTTPError, ValueError) as error:
            raise AppError(503, "MODEL_SERVICE_UNAVAILABLE", "Model service unavailable") from error
