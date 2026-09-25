"""Export the canonical API schema without starting external services."""

import json
from pathlib import Path

from risk_api.main import app


def main() -> None:
    target = Path(__file__).resolve().parents[3] / "contracts" / "openapi.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )


if __name__ == "__main__":
    main()
