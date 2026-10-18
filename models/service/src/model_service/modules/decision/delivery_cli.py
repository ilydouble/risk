"""Local packaging and verified GitHub Release download/install commands."""

import argparse
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from zipfile import BadZipFile

from huggingface_hub import snapshot_download
from huggingface_hub.errors import HfHubHTTPError

from model_service.execution.contracts import ExecutionError
from model_service.modules.decision.artifacts.archive import install
from model_service.modules.decision.artifacts.delivery import install_delivery, package_delivery
from model_service.modules.decision.artifacts.manifest import Release, verify_bundle
from model_service.modules.decision.contracts.input import DEFINITION, ROOT


def download_assets(release: Release, workspace: Path) -> None:
    if not shutil.which("gh"):
        raise ValueError("Install and authenticate GitHub CLI (gh) to download releases")
    if release.dataset is None:
        raise ValueError("Release does not declare a financial dataset")
    # gh handles authentication; Release availability is determined by GitHub, not a local flag.
    subprocess.run(
        [
            "gh", "release", "download", release.tag, "--repo", release.repository,
            "--pattern", release.asset, "--pattern", release.dataset.asset,
            "--dir", str(workspace),
        ],
        check=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("package", help="Prepare model and dataset assets; never upload")
    build.add_argument("--adapter", type=Path, required=True)
    build.add_argument("--dataset", type=Path, required=True, help="Packaged financial dataset ZIP")
    build.add_argument("--calibration", type=Path, help="Defaults to adapter/calibration.json")
    build.add_argument("--definition", type=Path, default=DEFINITION)
    build.add_argument("--output", type=Path, required=True)
    fetch = commands.add_parser("install", help="Download and install the model and financial data")
    fetch.add_argument("--release", type=Path, default=DEFINITION / "release.json")
    fetch.add_argument("--assets-dir", type=Path, help="Use local Release assets without GitHub")
    fetch.add_argument("--destination", type=Path)
    fetch.add_argument("--dataset-destination", type=Path)
    base_group = fetch.add_mutually_exclusive_group()
    base_group.add_argument("--base-from", type=Path, help="Copy a verified local base")
    base_group.add_argument("--with-base", action="store_true", help="Download the pinned HF base")
    check = commands.add_parser("verify", help="Verify a model directory and optional base")
    check.add_argument("--model-dir", type=Path, required=True)
    check.add_argument("--release", type=Path, default=DEFINITION / "release.json")
    check.add_argument("--base", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "package":
            release = package_delivery(
                args.adapter.resolve(), args.definition.resolve(), args.output.resolve(),
                dataset=args.dataset.resolve(),
                calibration=args.calibration.resolve() if args.calibration else None,
            )
            print(json.dumps(release.model_dump(), indent=2))
        elif args.command == "verify":
            release = Release.model_validate_json(args.release.read_bytes())
            manifest, _ = verify_bundle(args.model_dir, release, base=args.base)
            print(
                f"Verified {manifest.model.model_version}; base verified: {args.base is not None}"
            )
        else:
            release = Release.model_validate_json(args.release.read_bytes())
            if release.dataset is None:
                raise ValueError("Release does not declare a financial dataset")
            destination = (
                args.destination or ROOT / "models/weights" / release.model_version
            ).resolve()
            dataset_destination = (
                args.dataset_destination or ROOT / "datasets" / Path(release.dataset.asset).stem
            ).resolve()
            with tempfile.TemporaryDirectory(prefix="uk-model-download-") as temporary:
                workspace = Path(temporary)
                assets = args.assets_dir.resolve() if args.assets_dir else workspace
                if args.assets_dir is None:
                    download_assets(release, workspace)
                base = args.base_from.resolve() if args.base_from else None
                if args.with_base:
                    staged = workspace / "adapter-only"
                    install(assets / release.asset, staged, release)
                    manifest, _ = verify_bundle(staged, release)
                    base = destination / "base"
                    if not base.exists():
                        base = workspace / "base"
                        snapshot_download(
                            repo_id=manifest.model.base.repo_id,
                            revision=manifest.model.base.revision,
                            allow_patterns=list(manifest.model.base.files),
                            local_dir=base,
                            endpoint="https://huggingface.co",
                            token=False,
                        )
                dataset_zip = install_delivery(
                    assets, release, destination, dataset_destination, base_from=base
                )
            print(f"Installed {release.model_version}: {destination}")
            print(f"Dataset directory: {dataset_destination}")
            print(f"Upload this ZIP in the workbench: {dataset_zip}")
            if base is None and not (destination / "base").is_dir():
                print("Base model was not installed; inference requires a verified local base.")
    except (
        OSError, ValueError, tarfile.TarError, BadZipFile,
        ExecutionError, HfHubHTTPError, subprocess.CalledProcessError,
    ) as error:
        print(f"UK model delivery failed: {error}", file=sys.stderr)
        return 1
    return 0
