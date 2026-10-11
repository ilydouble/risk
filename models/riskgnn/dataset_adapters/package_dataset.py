"""Package a dataset version using a reviewed repository preset (no model imports)."""

import argparse
import json
from pathlib import Path

from jsonschema.exceptions import ValidationError

from riskgnn.dataset_adapters.delivery import catalog, preset_details
from riskgnn.dataset_adapters.packaging import package


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    preview = parser.add_mutually_exclusive_group()
    preview.add_argument("--list-presets", action="store_true")
    preview.add_argument("--show-preset", metavar="PRESET")
    parser.add_argument("--preset")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--dataset-version")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=JSON",
        help="Override a parameter allowed by the preset's config schema",
    )
    parser.add_argument("--validate", action="store_true", help="Run full model-side inspection")
    parser.add_argument(
        "--validation-python",
        type=Path,
        help="Python interpreter with model validation dependencies installed",
    )
    args = parser.parse_args()
    try:
        result: dict | list[dict]
        overrides = {}
        for item in args.set:
            key, separator, value = item.partition("=")
            if not separator or not key or key in overrides:
                raise ValueError("Each --set must be a unique KEY=JSON parameter")
            overrides[key] = json.loads(value)
        if (args.list_presets or args.show_preset) and any(
            value is not None
            for value in (
                args.preset,
                args.data_dir,
                args.dataset_version,
                args.output,
                args.validation_python,
            )
        ):
            parser.error("Preset preview cannot be combined with packaging arguments")
        if (args.list_presets or args.show_preset) and args.validate:
            parser.error("Preset preview does not perform data validation")
        if args.list_presets:
            if overrides:
                parser.error("Use --show-preset to preview parameter overrides")
            result = [preset_details(name) for d in catalog() for name in d.presets]
        elif args.show_preset:
            result = preset_details(args.show_preset, overrides)
        else:
            if any(
                value is None
                for value in (args.preset, args.data_dir, args.dataset_version, args.output)
            ):
                parser.error(
                    "packaging requires --preset, --data-dir, --dataset-version and --output"
                )
            result = package(
                args.data_dir,
                args.output,
                args.preset,
                args.dataset_version,
                overrides=overrides,
                validate=args.validate,
                validation_python=args.validation_python,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    except (ValueError, OSError, ValidationError) as error:
        parser.exit(2, f"Packaging error: {error}\n")


if __name__ == "__main__":
    main()
