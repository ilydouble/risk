from ipaddress import ip_address
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ModelConnection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(min_length=1, max_length=2048)
    model: str = Field(min_length=1, max_length=128)
    apiKey: str = Field(default="", max_length=4096)

    @field_validator("url")
    @classmethod
    def chat_completion_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        host = parsed.hostname
        _ = parsed.port
        if (
            parsed.scheme not in {"http", "https"}
            or not host
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"/v1/chat/completions", "/chat/completions"}
        ):
            raise ValueError("Provide an HTTP(S) chat/completions endpoint without credentials")
        if host.lower() in {"localhost", "metadata.google.internal"}:
            raise ValueError("Loopback and metadata endpoints are unavailable")
        try:
            address = ip_address(host)
        except ValueError:
            pass
        else:
            if (
                address.is_loopback
                or address.is_link_local
                or address.is_multicast
                or address.is_unspecified
            ):
                raise ValueError("Loopback and link-local endpoints are unavailable")
        return value
