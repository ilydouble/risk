"""Run bounded UK LoRA pilots with the user's copied JevForge implementation."""

import argparse
import gc
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

QUESTION = "formal_insolvency_12m"
REVISION = "c1899de289a04d12100db370d81485cdf75e47ca"
DEFAULT_MODEL = (
    "/root/autodl-tmp/turgutino/jev/hf/hub/models--Qwen--Qwen3-0.6B/snapshots/" + REVISION
)


def read(path):
    with path.open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def write(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def calibration_lines(index):
    """Keep all observations of connected companies and matched pairs together."""
    parent = {}

    def find(key):
        parent.setdefault(key, key)
        if parent[key] != key:
            parent[key] = find(parent[key])
        return parent[key]

    for row in index:
        a, b = find("company:" + row["company_id"]), find("pair:" + row["pair_id"])
        parent[max(a, b)] = min(a, b)
    return {
        row["line"] for row in index
        if int(hashlib.sha256(find("company:" + row["company_id"]).encode()).hexdigest(), 16)
        % 10 == 0
    }


def metrics(labels, probabilities):
    import numpy as np

    y, p = np.asarray(labels, dtype=int), np.asarray(probabilities, dtype=float)
    if set(y.tolist()) != {0, 1} or not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError("Metrics require both classes and finite probabilities in [0,1]")
    order = np.argsort(-p, kind="stable")
    sy, sp = y[order], p[order]
    ends = np.r_[np.flatnonzero(np.diff(sp)), len(sp) - 1]
    tp = np.cumsum(sy)[ends]
    fp = ends + 1 - tp
    recall, fpr = tp / y.sum(), fp / (len(y) - y.sum())
    precision = tp / (tp + fp)
    auc = np.trapezoid(np.r_[0, recall], np.r_[0, fpr])
    ap = (np.diff(np.r_[0, recall]) * precision).sum()
    pred = p >= 0.5
    tn, fp_n = int(((y == 0) & ~pred).sum()), int(((y == 0) & pred).sum())
    fn, tp_n = int(((y == 1) & ~pred).sum()), int(((y == 1) & pred).sum())
    clipped = np.clip(p, 1e-7, 1 - 1e-7)
    return {
        "n": len(y), "roc_auc": float(auc), "pr_auc_average_precision": float(ap),
        "ks": float((recall - fpr).max()), "brier": float(((p - y) ** 2).mean()),
        "log_loss": float(-(y * np.log(clipped) + (1 - y) * np.log1p(-clipped)).mean()),
        "accuracy": (tp_n + tn) / len(y), "precision": tp_n / max(1, tp_n + fp_n),
        "recall": tp_n / max(1, tp_n + fn),
        "f1": 2 * tp_n / max(1, 2 * tp_n + fp_n + fn),
        "threshold": 0.5, "confusion_matrix": [[tn, fp_n], [fn, tp_n]],
    }


def temperature_fit(labels, probabilities):
    import numpy as np

    p = np.clip(np.asarray(probabilities), 1e-7, 1 - 1e-7)
    logits, y = np.log(p) - np.log1p(-p), np.asarray(labels)
    candidates = np.geomspace(0.05, 20, 241)
    losses = [float((np.logaddexp(0, logits / t) - y * logits / t).mean()) for t in candidates]
    return float(candidates[int(np.argmin(losses))])


def calibrated(probabilities, temperature):
    import numpy as np

    p = np.clip(np.asarray(probabilities), 1e-7, 1 - 1e-7)
    z = (np.log(p) - np.log1p(-p)) / temperature
    return np.exp(-np.logaddexp(0, -z)).tolist()


def examples(workspace, variant):
    from jevforge.data.schema import Example

    index = [r for r in read(workspace / "smoke/sample-index.jsonl") if r["split"] == "train"]
    calib = calibration_lines(index)
    groups = {}
    for split in ("train", "valid", "test"):
        converted = []
        for row in read(workspace / f"smoke/{split}.{variant}.jsonl"):
            q = row["questions"][QUESTION]
            labels = list(q["criteria"])
            converted.append(Example(
                json.dumps(row["state"], separators=(",", ":"), allow_nan=False),
                list(q["criteria"].values()), labels.index(row["expected"][QUESTION]),
                q["instructions"], "uk-research",
            ))
        groups[split] = converted
    groups["calibration"] = [e for i, e in enumerate(groups["train"], 1) if i in calib]
    groups["train"] = [e for i, e in enumerate(groups["train"], 1) if i not in calib]
    if not groups["train"] or not groups["calibration"]:
        raise ValueError("Empty training or calibration partition")
    return groups


def preflight(args):
    from jevforge.prompt import render
    from jevforge.trie import encode
    from transformers import AutoTokenizer

    root = args.workspace
    manifest = json.loads((root / "smoke/manifest.json").read_text())
    for name, info in manifest["files"].items():
        with (root / "smoke" / name).open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != info["sha256"]:
                raise ValueError("Dataset digest mismatch: " + name)
    tok = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    report = {"base_model": "Qwen/Qwen3-0.6B", "revision": REVISION, "variants": {}}
    for variant in ("financial", "graph"):
        report["variants"][variant] = {}
        for split, items in examples(root, variant).items():
            lengths = []
            for e in items:
                enc = encode(tok, render(tok, e.state, e.options, e.instruction), 2)
                lengths.append(len(enc.prompt_ids) + len(enc.trie.nodes))
            report["variants"][variant][split] = {
                "n": len(items), "positive": sum(e.gold for e in items),
                "max_tokens": max(lengths), "mean_tokens": sum(lengths) / len(lengths),
            }
            if max(lengths) > args.max_len:
                raise ValueError(f"{variant}/{split} exceeds token budget; refusing truncation")
    write(root / "results/preflight.json", report)
    print(json.dumps(report), flush=True)


def score(agent, items):
    import torch

    probabilities, labels, latency = [], [], []
    for i, e in enumerate(items):
        torch.cuda.synchronize()
        start = time.perf_counter()
        probs = agent.decide(e.state, e.options, e.instruction)
        torch.cuda.synchronize()
        latency.append(time.perf_counter() - start)
        probabilities.append(probs[1])
        labels.append(e.gold)
        if (i + 1) % 100 == 0:
            print(f"[score] {i + 1}/{len(items)}", flush=True)
    return labels, probabilities, latency


def evaluate(args):
    import torch
    from jevforge.jev import Jev

    variant, root = args.variant, args.workspace
    checkpoint = root / f"results/{variant}/adapter" if args.stage == "evaluate" else None
    agent = Jev.from_pretrained(args.model, adapter=str(checkpoint) if checkpoint else None,
                                device="cuda", dtype="bfloat16")
    groups = examples(root, variant)
    cal_y, cal_p, _ = score(agent, groups["calibration"])
    temperature = temperature_fit(cal_y, cal_p)
    report = {"variant": variant, "stage": args.stage, "temperature": temperature,
              "base_revision": REVISION, "calibration_n": len(cal_y), "splits": {}}
    for split in ("valid", "test"):
        labels, probabilities, times = score(agent, groups[split])
        adjusted = calibrated(probabilities, temperature)
        report["splits"][split] = {
            "raw": metrics(labels, probabilities), "calibrated": metrics(labels, adjusted),
            "samples_per_second": len(times) / sum(times),
            "mean_latency_ms": 1000 * sum(times) / len(times),
        }
        write(root / f"results/{variant}/{args.stage}.{split}.predictions.json", {
            "labels": labels, "probabilities": probabilities, "calibrated": adjusted,
        })
    # A saved adapter must reproduce predictions after an independent reload.
    if checkpoint:
        probes = groups["valid"][:5]
        before = [agent.decide(e.state, e.options, e.instruction) for e in probes]
        del agent
        gc.collect()
        torch.cuda.empty_cache()
        agent = Jev.from_pretrained(args.model, adapter=str(checkpoint), device="cuda",
                                    dtype="bfloat16")
        after = [agent.decide(e.state, e.options, e.instruction) for e in probes]
        error = max(abs(a - b) for x, y in zip(before, after, strict=True)
                    for a, b in zip(x, y, strict=True))
        report["reload_max_probability_error"] = error
        if error > 1e-5:
            raise ValueError("Adapter reload predictions changed")
    report["scoring_mode"] = agent.mode
    report["peak_allocated_gib"] = torch.cuda.max_memory_allocated() / 2**30
    report["peak_reserved_gib"] = torch.cuda.max_memory_reserved() / 2**30
    write(root / f"results/{variant}/{args.stage}.json", report)
    print(json.dumps(report), flush=True)


def train(args):
    import jevforge.train as training
    import torch

    root, variant = args.workspace, args.variant
    output = root / f"results/{variant}/adapter"
    if output.exists():
        raise ValueError("Refusing to overwrite an existing adapter")
    cfg = training.TrainConfig(
        model=args.model, out_dir=str(output), epochs=1, batch_size=args.batch_size,
        max_steps=args.max_steps, max_len=args.max_len, grad_checkpointing=True,
        save_every=0, seed=42, device="cuda", dtype="bfloat16",
    )
    training.train(cfg, examples(root, variant)["train"])
    result = json.loads((output / "train_result.json").read_text())
    result["peak_allocated_gib"] = torch.cuda.max_memory_allocated() / 2**30
    result["peak_reserved_gib"] = torch.cuda.max_memory_reserved() / 2**30
    write(root / f"results/{variant}/training-resource.json", result)
    if result["steps"] == 0:
        raise ValueError("Training performed no optimizer updates")
    print(json.dumps(result), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--stage", choices=["preflight", "baseline", "train", "evaluate", "run"],
                        default="run")
    parser.add_argument("--variant", choices=["financial", "graph"], default="financial")
    parser.add_argument("--max-steps", type=int, default=225)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-len", type=int, default=2048)
    parser.add_argument("--gpu-gib", type=float, default=6)
    args = parser.parse_args()
    if args.max_steps < 1 or args.batch_size < 1 or not math.isfinite(args.gpu_gib):
        raise ValueError("Invalid training budget")
    args.workspace = args.workspace.resolve()
    sys.path.insert(0, str(args.workspace / "jevforge"))
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    for variant in ("financial", "graph"):
        (args.workspace / f"results/{variant}").mkdir(parents=True, exist_ok=True)
    if args.stage == "run":
        stages = [("preflight", "financial")] + [
            (stage, variant) for variant in ("financial", "graph")
            for stage in ("baseline", "train", "evaluate")
        ]
        for stage, variant in stages:
            cmd = [sys.executable, str(Path(__file__).resolve()),
                   "--workspace", str(args.workspace),
                   "--stage", stage, "--variant", variant, "--model", args.model,
                   "--max-steps", str(args.max_steps), "--batch-size", str(args.batch_size),
                   "--max-len", str(args.max_len), "--gpu-gib", str(args.gpu_gib)]
            write(args.workspace / "results/status.json", {"stage": stage, "variant": variant})
            with (args.workspace / f"results/{variant}/{stage}.log").open("w") as log:
                subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, check=True)
        write(args.workspace / "results/status.json", {"stage": "complete"})
        return
    if args.stage == "preflight":
        preflight(args)
        return
    import torch

    total = torch.cuda.get_device_properties(0).total_memory
    torch.cuda.set_per_process_memory_fraction(min(0.9, args.gpu_gib * 2**30 / total))
    torch.cuda.reset_peak_memory_stats()
    if args.stage == "train":
        train(args)
    else:
        evaluate(args)


if __name__ == "__main__":
    main()
