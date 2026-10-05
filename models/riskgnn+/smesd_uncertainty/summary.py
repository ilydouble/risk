"""Summarize paired SMEsD uncertainty runs without selecting on test metrics."""

from __future__ import annotations

import argparse
import json
import zlib
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

METRICS = ("rocAuc", "prAuc", "brier", "f1")
PRIMARY_REFERENCE = "comrisk_noisy"
GATED_REFERENCES = (
    "riskgnn_noisy",
    "riskgnn_filter",
    "riskgnn_shuffled",
    "riskgnn_inverted",
)


def load_results(work_dirs: list[Path]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    seen: set[tuple[float, int, int, int, str]] = set()
    for work_dir in work_dirs:
        for path in sorted(work_dir.resolve().glob("runs/**/metrics.json")):
            result = json.loads(path.read_text(encoding="utf-8"))
            key = (
                float(result["scenario"]["noiseRatio"]),
                int(result["scenario"]["simulationSeed"]),
                int(result["seed"]),
                int(result["epochs"]),
                str(result["variant"]),
            )
            if key in seen:
                raise ValueError(f"duplicate run key {key}: {path}")
            seen.add(key)
            result["metricsPath"] = str(path)
            results.append(result)
    if not results:
        raise ValueError("no metrics.json files found")
    return results


def mean_interval(
    values: np.ndarray, bootstrap_samples: int, seed_label: str
) -> dict[str, float | int]:
    values = np.asarray(values, dtype=np.float64)
    if not np.isfinite(values).all():
        raise ValueError(f"non-finite metric values for {seed_label}")
    if len(values) == 1:
        lower = upper = float(values[0])
    else:
        seed = zlib.crc32(seed_label.encode("utf-8"))
        rng = np.random.default_rng(seed)
        sampled = rng.choice(
            values, size=(bootstrap_samples, len(values)), replace=True
        )
        boot_means = sampled.mean(axis=1)
        lower, upper = np.quantile(boot_means, [0.025, 0.975]).tolist()
    return {
        "n": len(values),
        "mean": float(values.mean()),
        "std": float(values.std(ddof=1)) if len(values) > 1 else 0.0,
        "ci95Lower": float(lower),
        "ci95Upper": float(upper),
    }


def summarize_groups(
    results: list[dict[str, Any]], bootstrap_samples: int
) -> list[dict[str, Any]]:
    groups: dict[tuple[float, str], list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        key = (float(result["scenario"]["noiseRatio"]), result["variant"])
        groups[key].append(result)

    summaries: list[dict[str, Any]] = []
    for (noise_ratio, variant), runs in sorted(groups.items()):
        row: dict[str, Any] = {
            "noiseRatio": noise_ratio,
            "variant": variant,
            "seeds": sorted(int(run["seed"]) for run in runs),
            "test": {},
        }
        for metric in METRICS:
            values = np.asarray([run["test"][metric] for run in runs])
            label = f"group:{noise_ratio}:{variant}:{metric}"
            row["test"][metric] = mean_interval(values, bootstrap_samples, label)
        summaries.append(row)
    return summaries


def summarize_comparisons(
    results: list[dict[str, Any]], bootstrap_samples: int
) -> list[dict[str, Any]]:
    by_run = {
        (
            float(result["scenario"]["noiseRatio"]),
            int(result["scenario"]["simulationSeed"]),
            int(result["seed"]),
            int(result["epochs"]),
            result["variant"],
        ): result
        for result in results
    }
    variants = sorted({result["variant"] for result in results})
    pairs = [
        (variant, PRIMARY_REFERENCE)
        for variant in variants
        if variant != PRIMARY_REFERENCE
    ]
    pairs.extend(("riskgnn_gated", reference) for reference in GATED_REFERENCES)

    comparisons: list[dict[str, Any]] = []
    noise_ratios = sorted(
        {float(result["scenario"]["noiseRatio"]) for result in results}
    )
    for noise_ratio in noise_ratios:
        for target, reference in pairs:
            matched: list[tuple[dict[str, Any], dict[str, Any]]] = []
            for key, target_result in by_run.items():
                noise, simulation_seed, train_seed, epochs, variant = key
                if noise != noise_ratio or variant != target:
                    continue
                reference_key = (
                    noise,
                    simulation_seed,
                    train_seed,
                    epochs,
                    reference,
                )
                if reference_key in by_run:
                    matched.append((target_result, by_run[reference_key]))
            if not matched:
                continue
            row: dict[str, Any] = {
                "noiseRatio": noise_ratio,
                "target": target,
                "reference": reference,
                "pairedSeeds": sorted(int(item[0]["seed"]) for item in matched),
                "testDelta": {},
            }
            for metric in METRICS:
                deltas = np.asarray(
                    [
                        target_run["test"][metric] - ref_run["test"][metric]
                        for target_run, ref_run in matched
                    ]
                )
                label = f"delta:{noise_ratio}:{target}:{reference}:{metric}"
                stats = mean_interval(deltas, bootstrap_samples, label)
                stats["favorableMean"] = (
                    -stats["mean"] if metric == "brier" else stats["mean"]
                )
                row["testDelta"][metric] = stats
            comparisons.append(row)
    return comparisons


def render_markdown(analysis: dict[str, Any]) -> str:
    lines = [
        "# SMEsD 边置信度实验汇总",
        "",
        "测试集仅用于最终报告；checkpoint 与阈值均由验证集确定。`Δ` 为目标变体减参考变体，Brier 越低越好。",
        "",
        "## 分组结果",
        "",
        "| 噪声率 | 变体 | n | ROC-AUC | PR-AUC | Brier | F1 |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for row in analysis["groups"]:
        metric = row["test"]
        lines.append(
            f"| {row['noiseRatio']:.2f} | `{row['variant']}` | "
            f"{metric['rocAuc']['n']} | {metric['rocAuc']['mean']:.4f} | "
            f"{metric['prAuc']['mean']:.4f} | {metric['brier']['mean']:.4f} | "
            f"{metric['f1']['mean']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## 配对差值",
            "",
            "| 噪声率 | 目标 | 参考 | n | ΔROC-AUC | ΔPR-AUC | ΔBrier |",
            "|---:|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in analysis["comparisons"]:
        metric = row["testDelta"]
        lines.append(
            f"| {row['noiseRatio']:.2f} | `{row['target']}` | "
            f"`{row['reference']}` | {metric['rocAuc']['n']} | "
            f"{metric['rocAuc']['mean']:+.4f} | {metric['prAuc']['mean']:+.4f} | "
            f"{metric['brier']['mean']:+.4f} |"
        )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dirs", type=Path, nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bootstrap-samples", type=int, default=10_000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results = load_results(args.work_dirs)
    analysis = {
        "protocolVersion": 1,
        "bootstrapSamples": args.bootstrap_samples,
        "runCount": len(results),
        "groups": summarize_groups(results, args.bootstrap_samples),
        "comparisons": summarize_comparisons(results, args.bootstrap_samples),
    }
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "analysis.json").write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "report.md").write_text(render_markdown(analysis), encoding="utf-8")
    print(json.dumps({"runCount": len(results), "outputDir": str(output_dir)}))


if __name__ == "__main__":
    main()
