"""Create a new contract-bearing ZIP without modifying the source archive."""

import argparse
import json
import shutil
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile

from riskgnn.dataset_adapters.contract import CONTRACT_NAME, read_contract


def package(source: Path, output: Path, dataset_id: str, version: str, adapter: str) -> None:
    if source.resolve() == output.resolve() or output.exists():
        raise ValueError("Use a new output ZIP path")
    marker = "company_attr.parquet" if adapter == "sg-comrisk" else "metadata.json"
    with ZipFile(source) as archive:
        infos = archive.infolist()
        roots = [
            PurePosixPath(item.filename).parent
            for item in infos
            if PurePosixPath(item.filename).name == marker
        ]
        if len(roots) != 1 or len(roots[0].parts) > 1:
            raise ValueError("Expected a single dataset root")
        if any(PurePosixPath(item.filename).name == CONTRACT_NAME for item in infos):
            raise ValueError("Source already has a dataset contract")
        contract = {
            "contract_version": 1,
            "dataset": {"id": dataset_id, "version": version},
            "adapter": {"id": adapter, "version": "1", "config": {}},
        }
        try:
            with ZipFile(output, "x", compression=ZIP_DEFLATED) as target:
                for info in infos:
                    with archive.open(info) as src, target.open(info, "w") as dst:
                        shutil.copyfileobj(src, dst, length=1024 * 1024)
                target.writestr(
                    (roots[0] / CONTRACT_NAME).as_posix(),
                    json.dumps(contract, indent=2),
                )
            read_contract(output)
        except Exception:
            output.unlink(missing_ok=True)
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--adapter", required=True, choices=["sg-comrisk", "bundle"])
    args = parser.parse_args()
    package(args.input, args.output, args.dataset_id, args.dataset_version, args.adapter)


if __name__ == "__main__":
    main()
