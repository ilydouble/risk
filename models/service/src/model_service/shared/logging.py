from os import getenv

from model_service.shared.config import Settings


def configure_logging(settings: Settings) -> None:
    import logging

    from stellarmesh_logging import JSONFormatter, PrettyFormatter

    handler = logging.StreamHandler()
    formatter = JSONFormatter if settings.log_format == "json" else PrettyFormatter
    handler.setFormatter(formatter(static_fields={"service": "riskgnn"}))
    logging.basicConfig(level=getenv("RISK_LOG_LEVEL", "INFO"), handlers=[handler], force=True)
