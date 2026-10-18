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
from scripts.prepare_uk_decisions import QUESTION, QUESTION_ID

REVISION = "c1899de289a04d12100db370d81485cdf75e47ca"
ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


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


def input_state(document: dict) -> str:
    if not isinstance(document, dict) or not isinstance(document.get("state"), dict):
        raise ValueError("Input requires a state object")
    state = document["state"]
    if set(state) != {"features"} or not isinstance(state["features"], dict):
        raise ValueError("The financial model requires state.features only")
    policy = json.loads((ROOT / "models/riskgnn/dataset_adapters/uk_dataset_v1/"
                         "feature-policy.json").read_text())
    numeric = {name for name in policy["numericFeatureAllowlist"]
               if not name.endswith("_missing") or name == "financial_missing"}
    categorical = set(policy["categoricalFeatureAllowlist"])
    for name, value in state["features"].items():
        if name in numeric:
            if not isinstance(value, (int, float, bool)) or not math.isfinite(value):
                raise ValueError(f"Invalid observed numeric feature: {name}")
        elif name in categorical:
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Invalid observed categorical feature: {name}")
        else:
            raise ValueError(f"Feature is outside the model input allowlist: {name}")
    if "questions" in document and document["questions"] != {QUESTION_ID: QUESTION}:
        raise ValueError("Questions must match the frozen training template")
    # Training serializes only state; labels and audit identifiers never enter the prompt.
    return json.dumps(state, separators=(",", ":"), allow_nan=False)


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
    state = input_state(read_input(args.input, args.line))
    base, adapter = args.base.resolve(), args.adapter.resolve()
    for path in (base / "config.json", base / "model.safetensors",
                 adapter / "adapter_config.json", adapter / "adapter_model.safetensors",
                 adapter / "decision_runtime.json"):
        if not path.is_file():
            raise ValueError(f"Required local model file is missing: {path}")
    device = ("cuda" if torch.cuda.is_available() else "cpu") if args.device == "auto" \
        else args.device
    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA was requested but is unavailable in this Python environment")
    dtype = args.dtype or ("bfloat16" if device == "cuda" else "float32")
    started = time.perf_counter()
    raw, tokenizer = load_decision_model(str(base), adapter, device=device, dtype=dtype)
    model = Jev(raw, tokenizer, mode="tree")
    encoded = model.encode(state, list(QUESTION["criteria"].values()), QUESTION["instructions"])
    tokens = len(encoded.prompt_ids) + len(encoded.trie.nodes)
    if tokens > 2048:
        raise ValueError("Input exceeds the trained 2048-token budget; truncation is disabled")
    if device == "cuda":
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
    load_seconds = time.perf_counter() - started
    started = time.perf_counter()
    with torch.inference_mode():
        probabilities = model.decide(
            state, list(QUESTION["criteria"].values()), QUESTION["instructions"],
        )
    if device == "cuda":
        torch.cuda.synchronize()
    inference_seconds = time.perf_counter() - started
    if (len(probabilities) != 2 or not all(math.isfinite(p) and 0 <= p <= 1
                                         for p in probabilities)
            or not math.isclose(sum(probabilities), 1, abs_tol=1e-5)):
        raise ValueError("Model returned invalid candidate probabilities")
    labels = list(QUESTION["criteria"])
    temperature = None
    adjusted = None
    if args.calibration:
        temperature = float(json.loads(args.calibration.read_text())["temperature"])
        adjusted = dict(zip(labels, calibrated(probabilities, temperature), strict=True))
    return {
        "model": "Qwen3-0.6B UK financial LoRA", "expectedBaseRevision": REVISION,
        "baseConfigSha256": digest(base / "config.json"),
        "device": device, "dtype": dtype, "scoringMode": "tree",
        "questionId": QUESTION_ID, "target": QUESTION["instructions"],
        "rawProbabilities": dict(zip(labels, probabilities, strict=True)),
        "calibratedProbabilities": adjusted, "temperature": temperature,
        "inputTokensIncludingCandidates": tokens,
        "stateSha256": hashlib.sha256(state.encode()).hexdigest(),
        "adapterSha256": digest(adapter / "adapter_model.safetensors"),
        "runtimeSha256": digest(adapter / "decision_runtime.json"),
        "loadSeconds": round(load_seconds, 4),
        "inferenceSeconds": round(inference_seconds, 4),
        "peakAllocatedMiB": round(torch.cuda.max_memory_allocated() / 1024**2, 2)
        if device == "cuda" else None,
        "limitations": [
            "Matched research-cohort scores are not population default probabilities.",
            "CPU/dtype/batch changes require separate numerical validation.",
            "No calibration is applied unless --calibration is supplied.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True,
                        help="JSON object or original financial JSONL; expected is ignored")
    parser.add_argument("--line", type=int, default=1)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--dtype", choices=("float32", "bfloat16", "float16"))
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--calibration", type=Path)
    args = parser.parse_args()
    if args.threads < 1:
        parser.error("--threads must be positive")
    try:
        print(json.dumps(predict(args), ensure_ascii=False, allow_nan=False, indent=2))
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Prediction failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
