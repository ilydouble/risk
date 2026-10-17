from dataclasses import dataclass, field
from enum import StrEnum
from os import getenv


class LlmConnectionType(StrEnum):
    QWEN_SELF_HOSTED = "qwen_self_hosted"
    MINIMAX = "minimax"


def _llm_thinking_enabled() -> bool:
    value = getenv("RISK_LLM_THINKING_ENABLED", "false").strip().lower()
    if value not in {"true", "false"}:
        raise ValueError("RISK_LLM_THINKING_ENABLED must be true or false")
    return value == "true"


@dataclass(frozen=True)
class Settings:
    database_url: str = getenv("DATABASE_URL", "postgresql+asyncpg://risk:risk@localhost:5432/risk")
    redis_url: str = getenv("REDIS_URL", "redis://localhost:6379/0")
    neo4j_uri: str = getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user: str = getenv("NEO4J_USER", "neo4j")
    neo4j_password: str = getenv("NEO4J_PASSWORD", "risk-demo-password")
    storage_bucket: str = getenv("STORAGE_BUCKET", "risk-documents")
    storage_endpoint: str = getenv("STORAGE_ENDPOINT", "http://localhost:9000")
    storage_public_endpoint: str = getenv("STORAGE_PUBLIC_ENDPOINT", "http://localhost:19000")
    storage_region: str = getenv("STORAGE_REGION", "us-east-1")
    cookie_secure: bool = getenv("COOKIE_SECURE", "false").lower() == "true"
    allowed_origin: str = getenv("ALLOWED_ORIGIN", "http://localhost:18080,http://localhost:3000")
    log_level: str = getenv("RISK_LOG_LEVEL", "INFO")
    log_format: str = getenv("RISK_LOG_FORMAT", "json")
    llm_url: str = getenv("RISK_LLM_URL", "http://172.16.4.3:8080/v1/chat/completions")
    llm_api_key: str = getenv("RISK_LLM_API_KEY", "")
    llm_model: str = getenv("RISK_LLM_MODEL", "Qwen3.6-35B-A3B")
    llm_connection_type: LlmConnectionType = field(
        default_factory=lambda: LlmConnectionType(
            getenv("RISK_LLM_CONNECTION_TYPE", "qwen_self_hosted")
        )
    )
    llm_thinking_enabled: bool = field(default_factory=_llm_thinking_enabled)
    preparation_runner_url: str = getenv("PREPARATION_RUNNER_URL", "http://localhost:8090")
    preparation_runner_token: str = getenv(
        "PREPARATION_RUNNER_TOKEN", "local-preparation-change-me")
    model_service_url: str = getenv("RISK_GNN_URL", "http://localhost:8001")
    model_service_token: str = getenv("RISK_GNN_API_TOKEN", "local-riskgnn-change-me")
    model_storage_bucket: str = getenv("MODELING_STORAGE_BUCKET", "risk-modeling")
    model_storage_key: str = getenv("MODELING_STORAGE_ACCESS_KEY", "RISKMODELINGAPP2026")
    model_storage_secret: str = getenv("MODELING_STORAGE_SECRET_KEY", "local-modeling-change-me")


settings = Settings()
