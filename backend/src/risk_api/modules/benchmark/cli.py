import argparse
import json
from pathlib import Path

from .engine.data import Dataset, dump_json
from .engine.demo import generate
from .engine.pipeline import Predictor, load_data, train


def main():
    parser = argparse.ArgumentParser(description="ComRisk-inspired v1 research CLI")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo")
    demo.add_argument("--output", default="data/processed/demo.json")
    demo.add_argument("--nodes", type=int, default=360)
    demo.add_argument("--seed", type=int, default=42)
    validate = commands.add_parser("validate")
    validate.add_argument("--data", required=True)
    fit = commands.add_parser("train")
    fit.add_argument("--data", required=True)
    fit.add_argument("--output", default="artifacts/demo")
    fit.add_argument("--epochs", type=int, default=100)
    fit.add_argument("--patience", type=int, default=15)
    fit.add_argument("--hidden", type=int, default=32)
    fit.add_argument("--layers", type=int, default=2)
    fit.add_argument("--seed", type=int, default=42)
    fit.add_argument(
        "--mode", choices=["full", "no_graph", "no_hyper", "self_only"], default="full"
    )
    fit.add_argument("--no-prior", action="store_true")
    fit.add_argument("--pretrain-epochs", type=int, default=0)
    predict = commands.add_parser("predict")
    predict.add_argument("--data", required=True)
    predict.add_argument("--model", required=True)
    predict.add_argument("--ids", nargs="*")
    predict.add_argument("--output", default="predictions.json")
    args = parser.parse_args()
    if args.command == "demo":
        generate(args.nodes, args.seed).write(args.output)
        print(f"Synthetic demo written to {args.output}")
    elif args.command == "validate":
        d = Dataset.read(args.data)
        print(
            json.dumps(
                {
                    "name": d.name,
                    "nodes": len(d.nodes),
                    "edges": len(d.edges),
                    "hyperedges": len(d.hyperedges),
                    "synthetic": d.synthetic,
                },
                ensure_ascii=False,
            )
        )
    elif args.command == "train":
        report = train(
            load_data(args.data),
            args.output,
            args.epochs,
            args.patience,
            args.seed,
            args.hidden,
            args.layers,
            args.mode,
            not args.no_prior,
            args.pretrain_epochs,
        )
        print(
            json.dumps(
                {
                    "model_test": report["model"]["test"],
                    "baseline_test": report["baselines"]["logistic"]["test"],
                },
                indent=2,
            )
        )
    else:
        result = Predictor(args.model).predict(Dataset.read(args.data), args.ids)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        dump_json(args.output, result)
        print(f"Wrote {len(result['predictions'])} predictions to {args.output}")


if __name__ == "__main__":
    main()
