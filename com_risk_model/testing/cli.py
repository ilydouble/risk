"""Local model validation, inference and offline evaluation (not pytest tests)."""

import argparse
import json
from pathlib import Path

import torch
from com_risk_runtime.artifacts import validate_bundle
from com_risk_runtime.explain import explain
from com_risk_runtime.predictor import Predictor
from com_risk_runtime.schema import Dataset

from training.evaluation import metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="ComRisk local inference and evaluation")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "predict", "explain", "evaluate"):
        command = commands.add_parser(name)
        command.add_argument("--data", type=Path, required=True)
        command.add_argument("--model", type=Path, required=name != "validate")
        command.add_argument("--output", type=Path)
        if name == "predict":
            command.add_argument("--ids", nargs="*")
        elif name == "explain":
            command.add_argument("--id", required=True)
        elif name == "evaluate":
            command.add_argument("--split", choices=["train", "valid", "test"], default="test")
    args = parser.parse_args()
    torch.set_num_threads(1)
    bundle = validate_bundle(args.model, args.data) if args.model else None
    dataset = bundle.dataset if bundle else Dataset.read(args.data)
    if args.command == "validate":
        result = {
            "name": dataset.name,
            "nodes": len(dataset.nodes),
            "edges": len(dataset.edges),
            "hyperedges": len(dataset.hyperedges),
            "synthetic": dataset.synthetic,
            "model_version": bundle.manifest.model_version if bundle else None,
        }
    else:
        predictor = Predictor(args.model)
        if args.command == "predict":
            result = predictor.predict(dataset, args.ids)
        elif args.command == "explain":
            result = explain(predictor, dataset, args.id)
        else:
            nodes = [n for n in dataset.nodes if n.split == args.split]
            if not nodes:
                raise ValueError(f"no labelled companies in {args.split} split")
            prediction = predictor.predict(dataset, [n.id for n in nodes])
            result = metrics(
                [n.label for n in nodes],
                [row["risk_probability"] for row in prediction["predictions"]],
                predictor.meta["threshold"],
            )
    content = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")


if __name__ == "__main__":
    main()
