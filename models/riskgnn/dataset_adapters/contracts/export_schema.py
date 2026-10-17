"""Regenerate the inspect result schema advertised to the execution service."""

import json
from pathlib import Path

from riskgnn.dataset_adapters.contracts.operation import InspectionOutput


def main() -> None:
    descriptor = Path(__file__).resolve().parents[2] / "runtime.json"
    value = json.loads(descriptor.read_text())
    value["operations"]["inspect"]["result_schema"] = InspectionOutput.model_json_schema()
    descriptor.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
