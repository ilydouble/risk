"""Configure logging before Uvicorn starts the API."""

import uvicorn

from risk_api.shared.config import settings
from risk_api.shared.logging import configure_logging


def main() -> None:
    configure_logging(settings.log_level, output_format=settings.log_format)
    uvicorn.run("risk_api.main:app", host="0.0.0.0", port=8000, log_config=None, access_log=False)


if __name__ == "__main__":
    main()
