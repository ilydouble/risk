import hashlib
import json
import secrets
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from redis.asyncio import Redis
from redis.exceptions import RedisError

from risk_api.modules.auth.errors import AuthError
from risk_api.modules.auth.repository import UserRepository

SESSION_SECONDS = 8 * 60 * 60
COOKIE_NAME = "risk_sid"


def session_key(token: str) -> str:
    return f"risk:session:v1:{hashlib.sha256(token.encode()).hexdigest()}"


class AuthService:
    def __init__(self, users: UserRepository, redis: Redis):
        self.users = users
        self.redis = redis
        self.hasher = PasswordHasher()

    async def login(self, username: str, password: str) -> tuple[str, dict[str, Any]]:
        user = await self.users.by_username(username)
        try:
            valid = user is not None and self.hasher.verify(user.password_hash, password)
        except VerifyMismatchError:
            valid = False
        if not valid or user is None:
            raise AuthError("INVALID_CREDENTIALS")
        token = secrets.token_urlsafe(48)
        identity = {
            "version": 1,
            "user_id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "roles": ["demo"],
        }
        try:
            await self.redis.set(session_key(token), json.dumps(identity), ex=SESSION_SECONDS)
        except RedisError as error:
            raise AuthError("STORE_UNAVAILABLE") from error
        return token, identity

    async def identity(self, token: str | None) -> dict[str, Any]:
        if not token:
            raise AuthError("SESSION_EXPIRED")
        try:
            payload = await self.redis.get(session_key(token))
        except RedisError as error:
            raise AuthError("STORE_UNAVAILABLE") from error
        if not payload:
            raise AuthError("SESSION_EXPIRED")
        try:
            identity: dict[str, Any] = json.loads(payload)
        except (json.JSONDecodeError, TypeError) as error:
            raise AuthError("STORE_INVALID") from error
        if identity.get("version") != 1 or not identity.get("user_id"):
            raise AuthError("STORE_INVALID")
        return identity

    async def logout(self, token: str | None) -> None:
        if not token:
            return
        try:
            await self.redis.delete(session_key(token))
        except RedisError as error:
            raise AuthError("STORE_UNAVAILABLE") from error

    async def authorize(self, token: str | None, user_id: str | None) -> dict[str, Any]:
        identity = await self.identity(token)
        if user_id != identity["user_id"]:
            raise AuthError("SESSION_EXPIRED")
        return identity
