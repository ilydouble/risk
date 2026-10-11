"""Package a concrete dataset directory or ZIP; never execute source attachments."""

import argparse
import json
import shutil
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile

from riskgnn.dataset_adapters.contract import CONTRACT_NAME, read_contract

MARKERS = {
    "sg-comrisk": "company_attr.parquet",
    "smesd": "train.json",
    "uk-dataset-v1": "train.json",
}


def package(
    source: Path,
    output: Path,
    dataset_id: str,
    version: str,
    adapter: str,
    *,
    config: dict | None = None,
) -> None:
    if source.resolve() == output.resolve() or output.exists():
        raise ValueError("Use a new output ZIP path")
    marker = MARKERS[adapter]
    contract = {
        "contract_version": 1,
        "dataset": {"id": dataset_id, "version": version},
        "adapter": {"id": adapter, "version": "1", "config": config or {}},
    }
    if source.is_dir():
        if not (source / marker).is_file():
            raise ValueError("Select one dataset directory, not the combined delivery folder")
        files = sorted(source.rglob("*"))
        if any(p.is_symlink() for p in files) or any(p.name == CONTRACT_NAME for p in files):
            raise ValueError("Source contains links or already has a dataset contract")
        if output.resolve().is_relative_to(source.resolve()):
            raise ValueError("Output must be outside the source directory")
        try:
            with ZipFile(output, "x", compression=ZIP_DEFLATED) as target:
                for path in files:
                    if path.is_file():
                        target.write(path, path.relative_to(source))
                target.writestr(CONTRACT_NAME, json.dumps(contract, indent=2))
            read_contract(output)
        except Exception:
            output.unlink(missing_ok=True)
            raise
        return
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
    parser.add_argument("--adapter", required=True, choices=list(MARKERS))
    parser.add_argument(
        "--target-count", type=int, help="Bounded training targets; splits retained"
    )
    args = parser.parse_args()
    config = {"target_count": args.target_count} if args.target_count is not None else {}
    package(
        args.input, args.output, args.dataset_id, args.dataset_version, args.adapter, config=config
    )


if __name__ == "__main__":
    main()
