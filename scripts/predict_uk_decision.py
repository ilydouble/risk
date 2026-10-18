"""Load the frozen UK financial decision model for local, offline inference."""

import argparse
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

import torch
from jevforge import Jev

from scripts.jevforge_runtime import load_decision_model
from scripts.uk_decision.input_contract import DEFINITION, input_state, load_contract
from scripts.uk_decision.manifest import Release, digest, verify_bundle

REVISION = "c1899de289a04d12100db370d81485cdf75e47ca"


def read_input(path: Path, line: int = 1) -> dict:
    if line < 1:
        raise ValueError("Input line must be positive")
    with path.open(encoding="utf-8-sig") as stream:
        if path.suffix.lower() == ".jsonl":
            for _ in range(line):
                content = stream.readline(1024 * 1024 + 1)
                if not content:
                    raise ValueError("Input line does not exist")
                if len(content) > 1024 * 1024:
                    raise ValueError("Input exceeds 1 MiB")
        else:
            if line != 1:
                raise ValueError("--line only applies to JSONL inputs")
            content = stream.read(1024 * 1024 + 1)
    if len(content) > 1024 * 1024:
        raise ValueError("Input exceeds 1 MiB")
    return json.loads(content)


def calibrated(probabilities: list[float], temperature: float) -> list[float]:
    if not math.isfinite(temperature) or temperature <= 0:
        raise ValueError("Calibration temperature must be finite and positive")
    p = min(max(probabilities[1], 1e-7), 1 - 1e-7)
    z = (math.log(p) - math.log1p(-p)) / temperature
    adjusted = 1 / (1 + math.exp(-z)) if z >= 0 else math.exp(z) / (1 + math.exp(z))
    return [1 - adjusted, adjusted]


def predict(args: argparse.Namespace) -> dict:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    torch.set_num_threads(args.threads)
    calibration_path = args.calibration
    revision = REVISION
    if args.model_dir:
        root = args.model_dir.resolve()
        base = args.base.resolve() if args.base else root / "base"
        release = Release.model_validate_json(args.release.read_bytes())
        manifest, contract = verify_bundle(root, release, base=base)
        revision = manifest.model.base.revision
        adapter = root / "adapter"
        calibration_path = (
            root / "calibration.json" if "calibration.json" in manifest.files else None
        )
    else:
        contract = load_contract()
        base, adapter = args.base.resolve(), args.adapter.resolve()
    state = input_state(read_input(args.input, args.line), contract)
    for path in (
        base / "config.json",
        base / "model.safetensors",
        adapter / "adapter_config.json",
        adapter / "adapter_model.safetensors",
        adapter / "decision_runtime.json",
    ):
        if not path.is_file():
            raise ValueError(f"Required local model file is missing: {path}")
    device = (
        ("cuda" if torch.cuda.is_available() else "cpu") if args.device == "auto" else args.device
    )
    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA was requested but is unavailable in this Python environment")
    dtype = args.dtype or ("bfloat16" if device == "cuda" else "float32")
    started = time.perf_counter()
    raw, tokenizer = load_decision_model(str(base), adapter, device=device, dtype=dtype)
    model = Jev(raw, tokenizer, mode="tree")
    question = contract.question
    encoded = model.encode(state, list(question.criteria.values()), question.instructions)
    tokens = len(encoded.prompt_ids) + len(encoded.trie.nodes)
    if tokens > contract.max_tokens:
        raise ValueError("Input exceeds the trained 2048-token budget; truncation is disabled")
    if device == "cuda":
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
    load_seconds = time.perf_counter() - started
    started = time.perf_counter()
    with torch.inference_mode():
        probabilities = model.decide(
            state,
            list(question.criteria.values()),
            question.instructions,
        )
    if device == "cuda":
        torch.cuda.synchronize()
    inference_seconds = time.perf_counter() - started
    if (
        len(probabilities) != 2
        or not all(math.isfinite(p) and 0 <= p <= 1 for p in probabilities)
        or not math.isclose(sum(probabilities), 1, abs_tol=1e-5)
    ):
        raise ValueError("Model returned invalid candidate probabilities")
    labels = list(question.criteria)
    temperature = None
    adjusted = None
    if calibration_path:
        temperature = float(json.loads(calibration_path.read_text())["temperature"])
        adjusted = dict(zip(labels, calibrated(probabilities, temperature), strict=True))
    return {
        "model": "Qwen3-0.6B UK financial LoRA",
        "expectedBaseRevision": revision,
        "modelVersion": contract.model_version,
        "bundleVerified": args.model_dir is not None,
        "baseConfigSha256": digest(base / "config.json"),
        "device": device,
        "dtype": dtype,
        "scoringMode": "tree",
        "questionId": contract.question_id,
        "target": question.instructions,
        "rawProbabilities": dict(zip(labels, probabilities, strict=True)),
        "calibratedProbabilities": adjusted,
        "temperature": temperature,
        "inputTokensIncludingCandidates": tokens,
        "stateSha256": hashlib.sha256(state.encode()).hexdigest(),
        "adapterSha256": digest(adapter / "adapter_model.safetensors"),
        "runtimeSha256": digest(adapter / "decision_runtime.json"),
        "loadSeconds": round(load_seconds, 4),
        "inferenceSeconds": round(inference_seconds, 4),
        "peakAllocatedMiB": round(torch.cuda.max_memory_allocated() / 1024**2, 2)
        if device == "cuda"
        else None,
        "limitations": [
            "Matched research-cohort scores are not population default probabilities.",
            "CPU/dtype/batch changes require separate numerical validation.",
            "Calibration requires an explicit file or a versioned calibration artifact.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model-dir", type=Path, help="Verify and load a complete versioned bundle"
    )
    parser.add_argument("--release", type=Path, default=DEFINITION / "release.json")
    parser.add_argument("--base", type=Path, help="Defaults to MODEL_DIR/base in bundle mode")
    parser.add_argument("--adapter", type=Path, help="Legacy local debugging, without a bundle")
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="JSON object or original financial JSONL; expected is ignored",
    )
    parser.add_argument("--line", type=int, default=1)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--dtype", choices=("float32", "bfloat16", "float16"))
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--calibration", type=Path)
    args = parser.parse_args()
    if args.threads < 1:
        parser.error("--threads must be positive")
    if args.model_dir:
        if args.adapter or args.calibration:
            parser.error(
                "--model-dir uses its own adapter and calibration; overrides are not allowed"
            )
    elif not args.base or not args.adapter:
        parser.error("Use --model-dir or provide both --base and --adapter")
    try:
        print(json.dumps(predict(args), ensure_ascii=False, allow_nan=False, indent=2))
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Prediction failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
