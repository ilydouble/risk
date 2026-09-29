"""Run a resumable paired SMEsD edge-confidence experiment matrix."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from uncertainty_protocol import VARIANTS

HERE = Path(__file__).resolve().parent
SIMULATOR = HERE / "simulate_smesd_uncertainty.py"
TRAINER = HERE / "train_smesd_uncertainty.py"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def noise_slug(noise_ratio: float) -> str:
    return f"noise_{round(noise_ratio * 100):03d}"


def run_logged(command: list[str], log_path: Path, env: dict[str, str]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log:
        completed = subprocess.run(
            command,
            check=False,
            stdout=log,
            stderr=subprocess.STDOUT,
            env=env,
        )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed with exit {completed.returncode}; see {log_path}"
        )


def ensure_scenario(
    python: str,
    data_dir: Path,
    scenario_dir: Path,
    noise_ratio: float,
    seed: int,
    env: dict[str, str],
) -> dict[str, Any]:
    manifest_path = scenario_dir / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (
            manifest["simulationSeed"] != seed
            or not abs(manifest["noiseRatio"] - noise_ratio) < 1e-12
        ):
            raise ValueError(
                f"existing scenario does not match request: {scenario_dir}"
            )
        return manifest

    scenario_dir.mkdir(parents=True, exist_ok=True)
    command = [
        python,
        str(SIMULATOR),
        "--data-dir",
        str(data_dir),
        "--output-dir",
        str(scenario_dir),
        "--noise-ratio",
        str(noise_ratio),
        "--seed",
        str(seed),
    ]
    run_logged(command, scenario_dir / "generation.log", env)
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def collect_results(run_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(run_root.glob("noise_*/sim_*/train_*/*/metrics.json")):
        result = json.loads(path.read_text(encoding="utf-8"))
        row = {
            "noiseRatio": result["scenario"]["noiseRatio"],
            "simulationSeed": result["scenario"]["simulationSeed"],
            "trainSeed": result["seed"],
            "variant": result["variant"],
            "epochs": result["epochs"],
            "bestEpoch": result["bestEpoch"],
            "parameterCount": result["parameterCount"],
            "runtimeSeconds": result["runtimeSeconds"],
        }
        for split in ("validation", "test"):
            for metric, value in result[split].items():
                row[f"{split}_{metric}"] = value
        rows.append(row)
    return rows


def write_summary(work_dir: Path) -> None:
    rows = collect_results(work_dir / "runs")
    json_path = work_dir / "summary.json"
    csv_path = work_dir / "summary.csv"
    json_path.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if not rows:
        csv_path.write_text("", encoding="utf-8")
        return
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--noise-ratios", type=float, nargs="+", required=True)
    parser.add_argument("--seeds", type=int, nargs="+", required=True)
    parser.add_argument(
        "--variants", nargs="+", choices=sorted(VARIANTS), default=sorted(VARIANTS)
    )
    parser.add_argument("--epochs", type=int, default=500)
    parser.add_argument("--confidence-threshold", type=float, default=0.5)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--threads", type=int, default=0)
    parser.add_argument("--rerun", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if any(not 0 <= value <= 0.8 for value in args.noise_ratios):
        raise ValueError("all noise ratios must be within [0, 0.8]")
    data_dir = args.data_dir.resolve()
    work_dir = args.work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    if args.threads > 0:
        env["OMP_NUM_THREADS"] = str(args.threads)
        env["MKL_NUM_THREADS"] = str(args.threads)

    runner_manifest: dict[str, Any] = {
        "protocolVersion": 1,
        "dataDir": str(data_dir),
        "noiseRatios": args.noise_ratios,
        "pairedSeeds": args.seeds,
        "variants": args.variants,
        "epochs": args.epochs,
        "confidenceThreshold": args.confidence_threshold,
        "python": args.python,
        "threads": args.threads,
        "sourceSha256": {
            path.name: file_sha256(path)
            for path in (
                Path(__file__).resolve(),
                SIMULATOR,
                TRAINER,
                HERE / "uncertainty_protocol.py",
                HERE.parent / "riskgnn" / "gnn.py",
                HERE.parent / "riskgnn" / "utils.py",
            )
        },
    }
    matrix_manifest_path = work_dir / "matrix_manifest.json"
    if matrix_manifest_path.exists():
        existing_manifest = json.loads(matrix_manifest_path.read_text(encoding="utf-8"))
        comparable_existing = {
            key: value
            for key, value in existing_manifest.items()
            if key != "createdUnixSeconds"
        }
        if comparable_existing != runner_manifest:
            raise ValueError(
                "matrix configuration or source hashes changed; use a new work directory"
            )
    else:
        runner_manifest["createdUnixSeconds"] = time.time()
        matrix_manifest_path.write_text(
            json.dumps(runner_manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    try:
        for noise_ratio in args.noise_ratios:
            for seed in args.seeds:
                scenario_dir = (
                    work_dir / "scenarios" / noise_slug(noise_ratio) / f"seed_{seed}"
                )
                ensure_scenario(
                    args.python,
                    data_dir,
                    scenario_dir,
                    noise_ratio,
                    seed,
                    env,
                )
                for variant in args.variants:
                    output_dir = (
                        work_dir
                        / "runs"
                        / noise_slug(noise_ratio)
                        / f"sim_{seed}"
                        / f"train_{seed}"
                        / variant
                    )
                    metrics_path = output_dir / "metrics.json"
                    if metrics_path.exists() and not args.rerun:
                        print(f"SKIP {metrics_path}", flush=True)
                        continue
                    output_dir.mkdir(parents=True, exist_ok=True)
                    print(
                        f"START noise={noise_ratio:.2f} seed={seed} variant={variant}",
                        flush=True,
                    )
                    command = [
                        args.python,
                        str(TRAINER),
                        "--data-dir",
                        str(data_dir),
                        "--scenario-dir",
                        str(scenario_dir),
                        "--output-dir",
                        str(output_dir),
                        "--variant",
                        variant,
                        "--seed",
                        str(seed),
                        "--n-epoch",
                        str(args.epochs),
                        "--confidence-threshold",
                        str(args.confidence_threshold),
                    ]
                    run_logged(command, output_dir / "train.log", env)
                    result = json.loads(metrics_path.read_text(encoding="utf-8"))
                    print(
                        f"DONE variant={variant} test_auc={result['test']['rocAuc']:.6f} "
                        f"test_pr_auc={result['test']['prAuc']:.6f}",
                        flush=True,
                    )
                    write_summary(work_dir)
    finally:
        write_summary(work_dir)


if __name__ == "__main__":
    main()
