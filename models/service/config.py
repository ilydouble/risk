from dataclasses import dataclass, field
from os import getenv
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_url: str = field(
        default_factory=lambda: getenv(
            "RISK_GNN_DATABASE_URL", "postgresql+asyncpg://riskgnn:riskgnn@localhost:15432/riskgnn"
        )
    )
    token: str = field(
        default_factory=lambda: getenv("RISK_GNN_API_TOKEN", "local-riskgnn-change-me")
    )
    workspace: Path = field(
        default_factory=lambda: Path(getenv("RISK_GNN_WORKSPACE", "runs/service"))
    )
    endpoint: str = field(
        default_factory=lambda: getenv("STORAGE_ENDPOINT", "http://localhost:19000")
    )
    bucket: str = field(default_factory=lambda: getenv("MODELING_STORAGE_BUCKET", "risk-modeling"))
    log_format: str = field(default_factory=lambda: getenv("RISK_LOG_FORMAT", "pretty"))


def configure_logging(settings: Settings) -> None:
    import logging

    from stellarmesh_logging import JSONFormatter, PrettyFormatter

    handler = logging.StreamHandler()
    formatter = JSONFormatter if settings.log_format == "json" else PrettyFormatter
    handler.setFormatter(formatter(static_fields={"service": "riskgnn"}))
    logging.basicConfig(level=getenv("RISK_LOG_LEVEL", "INFO"), handlers=[handler], force=True)
