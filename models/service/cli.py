import argparse
import json
from pathlib import Path
from typing import Any


def main() -> None:
    parser = argparse.ArgumentParser(description="RiskGNN model and service tools")
    parser.add_argument(
        "command",
        choices=[
            "validate-data",
            "prepare",
            "train",
            "test",
            "predict",
            "verify",
            "export",
            "serve",
        ],
    )
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--ids", nargs="+", default=[])
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--runner-id", default="riskgnn-node-edge")
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn

        uvicorn.run(
            "service.api.app:create_app", factory=True, host="0.0.0.0", port=8000, access_log=False
        )
        return
    if args.input is None:
        parser.error("--input is required")
    if args.command in {"validate-data", "prepare", "train", "export"} and args.output is None:
        parser.error("--output is required")
    from service.files import export_zip, verify

    result: Any = None
    if args.command == "validate-data":
        from service.datasets.dispatch import validate

        result = validate(args.input, args.output)
    elif args.command == "prepare":
        from service.adapters.prepare import prepare

        result = prepare(args.input, args.output)
    elif args.command == "train":
        from service.training.pipeline import train

        result = train(args.input, args.output, args.epochs, runner_id=args.runner_id)
    elif args.command == "test":
        from service.training.pipeline import evaluate

        result = evaluate(args.input)
    elif args.command == "predict":
        import torch

        from service.runtime.predictor import Predictor

        torch.set_num_threads(2)
        result = Predictor(args.input).predict(args.ids)
    elif args.command == "verify":
        result = verify(args.input, "riskgnn-model-v1")
    elif args.command == "export":
        export_zip(args.input, args.output)
    print(json.dumps({"kind": "result", "data": result}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
