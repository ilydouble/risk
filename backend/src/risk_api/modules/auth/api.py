from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Request, Response

from risk_api.config import settings
from risk_api.modules.auth.errors import LOGIN_ERRORS, LOGOUT_ERRORS, SESSION_ERRORS
from risk_api.modules.auth.service import COOKIE_NAME, SESSION_SECONDS, AuthService
from risk_api.schemas import (
    COMMON_ERROR_RESPONSES,
    ApiEnvelope,
    RequestLogin,
    RequestLogout,
    RequestMe,
    ResponseLogin,
    ResponseLogout,
    ResponseMe,
)

router = APIRouter(route_class=DishkaRoute)


@router.post(
    "/login", response_model=ApiEnvelope[ResponseLogin],
    responses=COMMON_ERROR_RESPONSES | LOGIN_ERRORS,
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
    return ApiEnvelope(
        code=200,
        internal_code="SUCCESS",
        message="Login successful",
        data=ResponseLogin(
            userId=identity["user_id"],
            username=identity["username"],
            displayName=identity["display_name"],
            expiresIn=SESSION_SECONDS,
        ),
    )


@router.post(
    "/logout", response_model=ApiEnvelope[ResponseLogout],
    responses=COMMON_ERROR_RESPONSES | LOGOUT_ERRORS,
)
async def logout(
    _: RequestLogout, request: Request, response: Response, service: FromDishka[AuthService]
) -> ApiEnvelope[ResponseLogout]:
    await service.logout(request.cookies.get(COOKIE_NAME))
    response.delete_cookie(COOKIE_NAME, path="/", secure=settings.cookie_secure, samesite="strict")
    return ApiEnvelope(
        code=200, internal_code="SUCCESS", message="Logged out", data=ResponseLogout(loggedOut=True)
    )


@router.post(
    "/me", response_model=ApiEnvelope[ResponseMe],
    responses=COMMON_ERROR_RESPONSES | SESSION_ERRORS,
)
async def me(
    _: RequestMe, request: Request, service: FromDishka[AuthService]
) -> ApiEnvelope[ResponseMe]:
    identity = await service.identity(request.cookies.get(COOKIE_NAME))
    return ApiEnvelope(
        code=200,
        internal_code="SUCCESS",
        message="OK",
        data=ResponseMe(
            userId=identity["user_id"],
            username=identity["username"],
            displayName=identity["display_name"],
        ),
    )
