import hmac
import logging
from uuid import uuid4

from fastapi import Request

from model_service.shared.api.response import error_response
from model_service.shared.config import Settings

logger = logging.getLogger("riskgnn.http")


def create_request_policy(settings: Settings):
    async def policy(request: Request, call_next):
        request.state.request_id = request.headers.get("X-Request-ID") or str(uuid4())
        if request.url.path.startswith("/internal/") and not hmac.compare_digest(
            request.headers.get("Authorization", ""), f"Bearer {settings.token}"
        ):
            return error_response(
                request, 401, "SERVICE_UNAUTHORIZED", "Invalid service credential"
            )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        logger.log(
            logging.DEBUG if request.url.path == "/health/live" else logging.INFO,
            "http.completed",
            extra={
                "request_id": request.state.request_id,
                "path": request.url.path,
                "status": response.status_code,
            },
        )
        return response

    return policy
