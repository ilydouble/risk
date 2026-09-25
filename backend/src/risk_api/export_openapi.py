"""Export the canonical API schema without starting external services."""

import json
from asyncio import run
from pathlib import Path

from risk_api.main import create_app


def main() -> None:
    app = create_app()
    try:
        target = Path(__file__).resolve().parents[3] / "contracts" / "openapi.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )
    finally:
        run(app.state.dishka_container.close())


if __name__ == "__main__":
    main()
