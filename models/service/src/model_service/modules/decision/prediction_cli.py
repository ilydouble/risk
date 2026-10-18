"""File I/O and command-line options for the same Predictor used by HTTP."""

import argparse
import json
import os
import sys
from pathlib import Path

import torch

from model_service.modules.decision.contracts.input import DEFINITION
from model_service.modules.decision.predictor import Predictor


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--release", type=Path, default=DEFINITION / "release.json")
    parser.add_argument("--base", type=Path)
    parser.add_argument("--adapter", type=Path)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--line", type=int, default=1)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--dtype", choices=("float32", "bfloat16", "float16"))
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--calibration", type=Path)
    args = parser.parse_args(argv)
    if not 1 <= args.threads <= 32:
        parser.error("--threads must be 1 to 32")
    if args.model_dir:
        if args.adapter or args.calibration:
            parser.error("--model-dir uses its own adapter and calibration")
    elif not args.base or not args.adapter:
        parser.error("Use --model-dir or provide both --base and --adapter")
    try:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
        torch.set_num_threads(args.threads)
        device = (
            ("cuda" if torch.cuda.is_available() else "cpu")
            if args.device == "auto"
            else args.device
        )
        dtype = args.dtype or ("bfloat16" if device == "cuda" else "float32")
        if args.model_dir:
            predictor = Predictor.load(
                args.model_dir.resolve(), args.release, device=device, dtype=dtype, base=args.base
            )
        else:
            predictor = Predictor.load_local(
                args.base.resolve(),
                args.adapter.resolve(),
                device=device,
                dtype=dtype,
                calibration=args.calibration,
            )
        result = predictor.score(read_input(args.input, args.line))
        print(result.model_dump_json(indent=2))
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Prediction failed: {error}", file=sys.stderr)
        return 1
    return 0
