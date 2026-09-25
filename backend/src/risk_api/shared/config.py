from dataclasses import dataclass
from os import getenv


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


settings = Settings()
