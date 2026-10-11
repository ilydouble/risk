import logging
from os import getenv

from stellarmesh_logging import JSONFormatter, PrettyFormatter

from model_service.shared.config import Settings


def configure_logging(settings: Settings) -> None:
    handler = logging.StreamHandler()
    formatter = JSONFormatter if settings.log_format == "json" else PrettyFormatter
    handler.setFormatter(formatter(static_fields={"service": "riskgnn"}))
    logging.basicConfig(level=getenv("RISK_LOG_LEVEL", "INFO"), handlers=[handler], force=True)
