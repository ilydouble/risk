from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class RequestRegister(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=3,
            max_length=32,
            pattern=r"^[A-Za-z0-9._-]+$",
        ),
    ]
    displayName: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
    ]
    password: str = Field(min_length=8, max_length=128)


class ResponseRegister(BaseModel):
    userId: str
    username: str
    displayName: str


class RequestLogin(BaseModel):
    username: str
    password: str


class ResponseLogin(BaseModel):
    userId: str
    username: str
    displayName: str
    expiresIn: int


class RequestLogout(BaseModel):
    pass


class ResponseLogout(BaseModel):
    loggedOut: bool


class RequestMe(BaseModel):
    pass


class ResponseMe(BaseModel):
    userId: str
    username: str
    displayName: str
