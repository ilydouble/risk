"""Local packaging and verified GitHub Release download/install commands."""

import argparse
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from huggingface_hub import snapshot_download

from scripts.uk_decision.archive import install, package
from scripts.uk_decision.input_contract import DEFINITION, ROOT
from scripts.uk_decision.manifest import Release, verify_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("package", help="Create a local Release asset; never upload")
    build.add_argument("--adapter", type=Path, required=True)
    build.add_argument("--definition", type=Path, default=DEFINITION)
    build.add_argument("--output", type=Path, required=True)
    fetch = commands.add_parser("install", help="Download a published asset or install a local one")
    fetch.add_argument("--release", type=Path, default=DEFINITION / "release.json")
    fetch.add_argument("--archive", type=Path, help="Install offline instead of downloading")
    fetch.add_argument("--destination", type=Path)
    base_group = fetch.add_mutually_exclusive_group()
    base_group.add_argument("--base-from", type=Path, help="Copy a verified local base")
    base_group.add_argument("--with-base", action="store_true", help="Download the pinned HF base")
    check = commands.add_parser("verify", help="Verify a model directory and optional base")
    check.add_argument("--model-dir", type=Path, required=True)
    check.add_argument("--release", type=Path, default=DEFINITION / "release.json")
    check.add_argument("--base", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "package":
            release = package(
                args.adapter.resolve(), args.definition.resolve(), args.output.resolve()
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
            destination = (
                args.destination or ROOT / "models/weights" / release.model_version
            ).resolve()
            with tempfile.TemporaryDirectory(prefix="uk-model-download-") as temporary:
                workspace = Path(temporary)
                archive = args.archive.resolve() if args.archive else workspace / release.asset
                if args.archive is None:
                    if release.publication_status != "published":
                        raise ValueError(
                            "Release is prepared locally, not published; use --archive"
                        )
                    if not shutil.which("gh"):
                        raise ValueError(
                            "Install and authenticate GitHub CLI (gh) to download releases"
                        )
                    # gh handles authentication without tokens in command arguments.
                    subprocess.run(
                        [
                            "gh",
                            "release",
                            "download",
                            release.tag,
                            "--repo",
                            release.repository,
                            "--pattern",
                            release.asset,
                            "--dir",
                            str(workspace),
                        ],
                        check=True,
                    )
                base = args.base_from.resolve() if args.base_from else None
                if args.with_base:
                    staged = workspace / "adapter-only"
                    install(archive, staged, release)
                    manifest, _ = verify_bundle(staged, release)
                    base = workspace / "base"
                    snapshot_download(
                        repo_id=manifest.model.base.repo_id,
                        revision=manifest.model.base.revision,
                        allow_patterns=list(manifest.model.base.files),
                        local_dir=base,
                    )
                install(archive, destination, release, base_from=base)
            print(f"Installed {release.model_version}: {destination}")
            if base is None:
                print("Base model was not installed; inference requires a verified local base.")
    except (OSError, ValueError, tarfile.TarError, subprocess.CalledProcessError) as error:
        print(f"UK model delivery failed: {error}", file=sys.stderr)
        return 1
    return 0
