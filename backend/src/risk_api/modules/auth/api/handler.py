from typing import Any

from dishka.integrations.fastapi import FromDishka
from fastapi import Request, Response

from risk_api.modules.auth.api.schemas import (
    RequestLogin,
    RequestLogout,
    RequestMe,
    RequestRegister,
    ResponseLogin,
    ResponseLogout,
    ResponseMe,
    ResponseRegister,
)
from risk_api.modules.auth.service import COOKIE_NAME, SESSION_SECONDS, AuthService
from risk_api.shared.api.envelope import ApiEnvelope
from risk_api.shared.api.response import success
from risk_api.shared.config import settings


async def authorize_request(request: Request, auth: AuthService) -> dict[str, Any]:
    return await auth.authorize(request.cookies.get(COOKIE_NAME), request.headers.get("X-User-ID"))


async def register(
    body: RequestRegister, service: FromDishka[AuthService]
) -> ApiEnvelope[ResponseRegister]:
    user = await service.register(body.username, body.password, body.displayName)
    return success(
        ResponseRegister(userId=user.id, username=user.username, displayName=user.display_name),
        message="Account created",
    )


async def login(
    body: RequestLogin, response: Response, service: FromDishka[AuthService]
) -> ApiEnvelope[ResponseLogin]:
    token, identity = await service.login(body.username, body.password)
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=SESSION_SECONDS,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )
    return success(
        ResponseLogin(
            userId=identity["user_id"],
            username=identity["username"],
            displayName=identity["display_name"],
            expiresIn=SESSION_SECONDS,
        ),
        message="Login successful",
    )


async def logout(
    _: RequestLogout, request: Request, response: Response, service: FromDishka[AuthService]
) -> ApiEnvelope[ResponseLogout]:
    await service.logout(request.cookies.get(COOKIE_NAME))
    response.delete_cookie(COOKIE_NAME, path="/", secure=settings.cookie_secure, samesite="strict")
    return success(ResponseLogout(loggedOut=True), message="Logged out")


async def me(
    _: RequestMe, request: Request, service: FromDishka[AuthService]
) -> ApiEnvelope[ResponseMe]:
    identity = await service.identity(request.cookies.get(COOKIE_NAME))
    return success(
        ResponseMe(
            userId=identity["user_id"],
            username=identity["username"],
            displayName=identity["display_name"],
        )
    )
