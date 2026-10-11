"""Export the canonical API schema without starting external services."""

import argparse
import json
from asyncio import run
from pathlib import Path

from model_service.app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("../contracts/riskgnn-openapi.json"))
    args = parser.parse_args()
    app = create_app()
    try:
        # Model commands run from models/; explicit output also supports installed wheels.
        target = args.output
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )
    finally:
        run(app.state.dishka_container.close())


if __name__ == "__main__":
    main()
