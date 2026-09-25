from pydantic import BaseModel


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
