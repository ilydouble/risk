"""Offline compatibility CLI for the existing Singapore overview pages."""

import argparse
import tempfile
from pathlib import Path

from riskgnn.dataset_adapters.acra.overview import build_singapore_overview
from riskgnn.dataset_adapters.registry import inspect
from riskgnn.workbench.artifacts import write_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sample-per-class", type=int, default=100)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="risk-acra-overview-") as temporary:
        validated = Path(temporary)
        result = inspect(args.source, validated)
        if result["protocol"] != "sg-comrisk-v1":
            raise ValueError("Overview requires an ACRA dataset")
        write_json(
            args.output, build_singapore_overview(validated, sample_per_class=args.sample_per_class)
        )


if __name__ == "__main__":
    main()
