"""Package a dataset version using a reviewed repository preset (no model imports)."""

import argparse
import json
import re
from pathlib import Path

from jsonschema.exceptions import ValidationError

from riskgnn.dataset_adapters.delivery import catalog, preset_details
from riskgnn.dataset_adapters.packaging import package

DEFAULT_OUTPUT_DIRECTORY = Path(__file__).resolve().parents[2] / "runs" / "datasets"


def default_output(preset: str, dataset_version: str) -> Path:
    # Do not silently rewrite version identifiers or allow them to create subdirectories.
    for value in (preset, dataset_version):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value):
            raise ValueError(
                "默认文件名要求预设和版本以字母或数字开头，仅含字母、数字、点、下划线、连字符；"
                "其他版本名称请通过 --output 指定输出文件"
            )
    return DEFAULT_OUTPUT_DIRECTORY / f"{preset}-{dataset_version}.zip"


def print_preset(details: dict) -> None:
    dataset, adapter = details["dataset"], details["adapter"]
    print(f"预设：{details['preset']}")
    print(f"数据集：{dataset.get('name', dataset['id'])}（{dataset['id']}）")
    print(f"适配器：{adapter['id']} / {adapter['version']}")
    print(f"说明：{details['description']}")
    print("必需文件：" + ", ".join(details["requiredFiles"]))
    print("预填配置：" + json.dumps(details["defaultConfig"], ensure_ascii=False))
    print("本次覆盖：" + json.dumps(details["overrides"], ensure_ascii=False))
    print("生效配置：" + json.dumps(details["config"], ensure_ascii=False))
    print("允许配置：" + json.dumps(details["configSchema"], ensure_ascii=False))
    print("打包必填：--preset、--data-dir、--dataset-version；--output 可选")
    print(f"默认输出：{DEFAULT_OUTPUT_DIRECTORY / (details['preset'] + '-<数据版本>.zip')}")


def print_summary(summary: dict) -> None:
    dataset, adapter = summary["contract"]["dataset"], summary["contract"]["adapter"]
    print("打包完成\n")
    print(f"数据集：{dataset.get('name', dataset['id'])}（{dataset['id']}）")
    print(f"数据版本：{dataset['version']}")
    print(f"适配器：{adapter['id']} / {adapter['version']}")
    print("契约：已自动生成 risk_dataset_contract.json")
    if summary["sourceContractIgnored"]:
        print("源契约：源文件保留，ZIP 内使用预设生成的新契约")
    print("配置：" + json.dumps(adapter["config"], ensure_ascii=False))
    if summary["validation"] == "full":
        print("校验范围：本地完整数据校验通过，上传后服务端仍会重新校验")
    else:
        print("校验范围：打包检查通过，完整数据校验将在上传后执行")
    print(f"文件数量：{summary['fileCount']}（含契约）")
    print(f"输出大小：{summary['sizeBytes']:,} 字节")
    print(f"输出文件：{summary['output']}")
    print("\n下一步：进入模型工作台 → 数据集 → 上传并校验")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    preview = parser.add_mutually_exclusive_group()
    preview.add_argument("--list-presets", action="store_true")
    preview.add_argument("--show-preset", metavar="PRESET")
    parser.add_argument("--preset")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--dataset-version")
    parser.add_argument(
        "--output", type=Path, help="输出 ZIP，默认 models/runs/datasets/<预设>-<版本>.zip"
    )
    parser.add_argument("--json", action="store_true", help="输出详细 JSON，供自动化脚本使用")
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
    args = parser.parse_args(argv)
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
            if any(value is None for value in (args.preset, args.data_dir, args.dataset_version)):
                parser.error("packaging requires --preset, --data-dir and --dataset-version")
            result = package(
                args.data_dir,
                args.output
                if args.output is not None
                else default_output(args.preset, args.dataset_version),
                args.preset,
                args.dataset_version,
                overrides=overrides,
                validate=args.validate,
                validation_python=args.validation_python,
            )
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        elif isinstance(result, list):
            for details in result:
                print_preset(details)
                print()
        elif args.show_preset:
            print_preset(result)
        else:
            print_summary(result)
    except (ValueError, OSError, ValidationError) as error:
        parser.exit(2, f"Packaging error: {error}\n")


if __name__ == "__main__":
    main()
