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
