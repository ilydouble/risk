"""Explicit full inspection; this command requires the model environment, but never trains."""

import argparse
import tempfile
from pathlib import Path

from riskgnn.dataset_adapters.registry import inspect
from riskgnn.workbench.artifacts import write_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="risk-dataset-inspect-") as work:
        result = inspect(args.input, Path(work))
        write_json(
            args.report,
            {
                key: result[key]
                for key in ("protocol", "sha256", "counts", "compatibility", "issues")
            },
        )


if __name__ == "__main__":
    main()
