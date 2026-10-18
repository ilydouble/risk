"""Model service entry points; command handlers share the packaged implementations."""

import argparse

import uvicorn

from model_service.modules.decision.delivery_cli import main as delivery_main
from model_service.modules.decision.prediction_cli import main as predict_main


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("serve")
    commands.add_parser("predict", add_help=False)
    commands.add_parser("delivery", add_help=False)
    args, remaining = parser.parse_known_args()
    if args.command == "predict":
        raise SystemExit(predict_main(remaining))
    if args.command == "delivery":
        raise SystemExit(delivery_main(remaining))
    if remaining:
        parser.error("Unrecognized serve arguments")
    uvicorn.run(
        "model_service.app:create_app", factory=True, host="0.0.0.0", port=8000, access_log=False
    )


if __name__ == "__main__":
    main()
