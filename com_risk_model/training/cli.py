"""Explicit model-development commands; never invoked by the application."""

import argparse
import json
from pathlib import Path

from .benchmark import run
from .data import load_data
from .demo import generate
from .export import export_bundle
from .fetch_smesd import fetch
from .pipeline import train
from .smesd import convert


def main() -> None:
    parser = argparse.ArgumentParser(description="ComRisk model development")
    commands = parser.add_subparsers(dest="command", required=True)
    download = commands.add_parser("fetch", help="download and verify pinned upstream data")
    download.add_argument("--output", type=Path, default=Path("data/raw/smesd"))
    prepare = commands.add_parser("prepare", help="convert SMEsD into disjoint snapshots")
    prepare.add_argument("--source", default="data/raw/smesd")
    prepare.add_argument("--output", default="data/processed/smesd")
    demo = commands.add_parser("demo", help="generate synthetic data for software checks")
    demo.add_argument("--output", default="data/processed/demo.json")
    demo.add_argument("--nodes", type=int, default=360)
    demo.add_argument("--seed", type=int, default=42)
    fit = commands.add_parser("train")
    fit.add_argument("--data", required=True)
    fit.add_argument("--output", default="runs/demo")
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
    benchmark = commands.add_parser("benchmark", help="run ablations, select on validation only")
    benchmark.add_argument("--data", default="data/processed/smesd")
    benchmark.add_argument("--output", default="runs/smesd-v1")
    benchmark.add_argument("--epochs", type=int, default=80)
    benchmark.add_argument("--seeds", nargs="+", type=int, default=[42])
    export = commands.add_parser("export", help="validate and package a selected run")
    export.add_argument("--run", type=Path, required=True)
    export.add_argument("--version", required=True)
    export.add_argument("--data", type=Path, required=True)
    export.add_argument("--output", type=Path, default=Path("runs/exports"))
    args = parser.parse_args()
    match args.command:
        case "fetch":
            fetch(args.output)
        case "prepare":
            print(json.dumps(convert(args.source, args.output), ensure_ascii=False, indent=2))
        case "demo":
            generate(args.nodes, args.seed).write(args.output)
            print(f"Synthetic demo written to {args.output}")
        case "train":
            report = train(
                load_data(args.data),
                args.output,
                epochs=args.epochs,
                patience=args.patience,
                seed=args.seed,
                hidden=args.hidden,
                layers=args.layers,
                mode=args.mode,
                use_prior=not args.no_prior,
                pretrain_epochs=args.pretrain_epochs,
            )
            print(json.dumps(report["model"], indent=2))
        case "benchmark":
            run(load_data(args.data), args.output, args.epochs, args.seeds)
        case "export":
            print(export_bundle(args.run, args.version, args.data, args.output))


if __name__ == "__main__":
    main()
