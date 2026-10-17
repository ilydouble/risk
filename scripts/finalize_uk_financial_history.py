"""Freeze the validated local financial-history extension and package its evidence."""

import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
import zlib
from collections import Counter
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from prepare_uk_basic_information import read_csv
from prepare_uk_financials import sha, write_json
from uk_financials.facts import ALIASES

ROOT = Path(__file__).resolve().parents[1]
CHECKED_FILES = [
    "features.csv",
    "labels.csv",
    "financial-history.csv",
    "financial-report-sources.csv",
    "history-facts.jsonl.gz",
    "history-source-facts.jsonl.gz",
    "history-quality-issues.jsonl.gz",
    "sample-history-links.csv",
    "history-report.json",
]


def finalize(base, output):
    validation_path = output / "validation.json"
    validation = json.loads(validation_path.read_text())
    if not validation["passed"]:
        raise ValueError("Independent full validation must pass first")
    if any(
        (output / name).stat().st_mtime_ns > validation_path.stat().st_mtime_ns
        for name in CHECKED_FILES
    ):
        raise ValueError("Validated inputs have changed; rerun the independent validator")
    report = json.loads((output / "history-report.json").read_text())
    if report["baseDeliverySha256"] != sha(base / "delivery-manifest.json"):
        raise ValueError("Base version changed")
    additional_ids = set()
    extra_bytes = 0
    for row in read_csv(output / "financial-report-sources.csv"):
        if row["period_end"] > row["availability_upper_bound"]:
            raise ValueError("Source report period ends after assumed availability")
        if row["is_v3_baseline_report"] != "False":
            continue
        source = Path(row["raw_cache_path"])
        raw = gzip.decompress(source.read_bytes())
        if hashlib.sha256(raw).hexdigest() != row["member_sha256"] or zlib.crc32(raw) != int(
            row["member_crc32"]
        ):
            raise ValueError("Additional raw filing checksum mismatch")
        destination = output / "sources/additional-filings" / row["report_id"][:2] / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        additional_ids.add(row["report_id"])
        extra_bytes += destination.stat().st_size
    source_counts, extra_samples, extra_used = Counter(), set(), set()
    for row in read_csv(output / "sample-history-links.csv"):
        if row["report_id"] in additional_ids:
            source_counts["additional_report_links"] += 1
            extra_samples.add(row["sample_id"])
            extra_used.add(row["report_id"])
        elif row["report_id"] == row["baseline_report_id"]:
            source_counts["selected_baseline_report_links"] += 1
        else:
            source_counts["other_v3_baseline_report_links"] += 1
    write_json(
        output / "packaging-report.json",
        {
            "bundledAdditionalRawReports": len(additional_ids),
            "bundledAdditionalRawBytes": extra_bytes,
            "samplesUsingAdditionalReports": len(extra_samples),
            "selectedAdditionalSourceReports": len(extra_used),
            "sourceLinks": source_counts,
        },
    )
    contract = json.loads((base / "feature-contract.json").read_text())
    numeric = [
        "financial_period_count",
        "financial_comparative_period_count",
        "financial_previous_gap_days",
        "financial_previous_missing",
    ]
    categorical = ["financial_previous_currency"]
    for metric in ALIASES:
        categorical.append(metric + "_previous_unit")
        for suffix in ["previous", "delta", "relative_change", "three_period_slope_per_year"]:
            numeric.extend([metric + "_" + suffix, metric + "_" + suffix + "_missing"])
    for ratio in ["current_ratio", "cash_ratio"]:
        for suffix in ["", "_previous", "_delta"]:
            numeric.extend([ratio + suffix, ratio + suffix + "_missing"])
    contract["numericFeatureAllowlist"] = list(
        dict.fromkeys(contract["numericFeatureAllowlist"] + numeric)
    )
    contract["categoricalFeatureAllowlist"] = list(
        dict.fromkeys(contract["categoricalFeatureAllowlist"] + categorical)
    )
    columns = next(read_csv(output / "features.csv")).keys()
    assert (
        set(contract["numericFeatureAllowlist"] + contract["categoricalFeatureAllowlist"])
        <= columns
    )
    contract.update(
        trendsUseOnlyInformationAvailableByBaselineDisclosure=True,
        zeroAndNegativePreviousValuesHaveNoRelativeGrowth=True,
        comparisonAndSlopeDatesAreAuditFieldsNotModelInputs=True,
        exactFilingDatesVerified=False,
    )
    write_json(output / "feature-contract.json", contract)
    doc = ROOT / "docs/architecture/uk-financial-history.md"
    shutil.copyfile(doc, output / doc.name)
    code_files = [
        ROOT / "scripts/extend_uk_financial_history.py",
        ROOT / "scripts/validate_uk_financial_history.py",
        ROOT / "scripts/finalize_uk_financial_history.py",
        ROOT / "scripts/prepare_uk_basic_information.py",
        ROOT / "scripts/prepare_uk_financials.py",
        ROOT / "scripts/prepare_uk_adverse_events.py",
        ROOT / "scripts/repair_uk_research_data.py",
        *sorted((ROOT / "scripts/uk_financials").glob("*.py")),
        ROOT / "scripts/tests/test_uk_financial_history.py",
        ROOT / "scripts/tests/test_uk_financials.py",
    ]
    for path in code_files:
        destination = output / "code" / path.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
    coverage = report["coverage"]
    (output / "README.md").write_text(
        f"""# 本地多期财务与趋势扩展 v1

这是叠加 `uk-research-graph-20261017-v3` 的独立财务扩展包。
`features.csv` 包含 v3 全部原观察字段及新增趋势字段，`labels.csv` 与 v3 完全一致。
图谱仍使用 v3 的企业 ID 和图文件；本轮未采集外部接口、未改变标签或图关系。

## 结果

- 核对并解析本地财报 {validation["sourceReports"]:,} 份，
  形成 {validation["historyRows"]:,} 条带披露版本的期间记录。
- 209,192 条观察全部保留：{coverage["samples_with_previous_period"]:,} 条有此前期间，
  {coverage["samples_with_any_comparable_delta"]:,} 条至少一项可比年度变化，
  {coverage["samples_with_any_three_period_slope"]:,} 条至少一项三期年化斜率。
- 额外缓存原财报 {len(additional_ids):,} 份随本包交付，其中 {len(extra_used):,} 份用于观察关联。

## 文件

- `features.csv`：v3 原字段＋上期值、年度差值、相对变化、三期斜率及流动/现金比率。
- `financial-history.csv`：每个来源财报和财务期末的独立版本，同一期间不重复计作年度。
- `financial-report-sources.csv`：原件摘要、CRC、大小、缓存位置、归档来源、保守可用日。
- `sample-history-links.csv`：每条观察采用的历史版本；同一公司同一期间只选一个整份披露版本。
- `history-facts.jsonl.gz`：清洗后事实；`history-source-facts.jsonl.gz`：校验前事实。
- `history-quality-issues.jsonl.gz`：质量处理与复核证据。
- `sources/additional-filings/`：额外财报原件的 gzip 副本，按报告 ID 前两位分目录。
- `history-report.json`、`trend-coverage.csv`、`validation.json`：覆盖与独立验证。
- `feature-contract.json`：可编码的候选字段，来源 ID、日期、状态说明等留作审计。

## 使用口径

“上期”按每项指标的日期、单位和期间选择，实际日期见该指标的 `_previous_period_end`；
相对变化是小数，例如 0.25 表示 25%。零或负基数留空相对变化，可比时仍保留绝对差值。
三期斜率使用真实日期间隔折算每年，仅在三期都满足比较条件时生成。

比较期数据的可用日沿用其来源财报的保守可用日，不能倒填成比较期末当日已知。
精确申报日仍未核实；本轮用户选择先做本地财报扩展，董事、PSC、抵押接口数据未新增。
v3 的 208,853 份原财报继续由原缓存/源数据包提供，本扩展只增装额外原件。
更多规则与限制见 `uk-financial-history.md`。
""",
        encoding="utf-8",
    )
    base_manifest = json.loads((base / "delivery-manifest.json").read_text())
    files = {
        str(path.relative_to(output)): {"bytes": path.stat().st_size, "sha256": sha(path)}
        for path in sorted(output.rglob("*"))
        if path.is_file() and path.name != "delivery-manifest.json"
    }
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    write_json(
        output / "delivery-manifest.json",
        {
            "format": "uk-local-financial-history-v1-delivery",
            "gitCommit": commit,
            "validated": True,
            "baseDirectory": str(base.resolve()),
            "baseDeliverySha256": sha(base / "delivery-manifest.json"),
            "baseSourceFinancialBundlesRetained": base_manifest["sourceFinancialBundlesRetained"],
            "additionalRawReportsBundled": len(additional_ids),
            "files": files,
        },
    )
    archive = output.with_suffix(".zip")
    temporary = archive.with_suffix(".zip.part")
    with ZipFile(
        temporary, "w", compression=ZIP_DEFLATED, compresslevel=6, allowZip64=True
    ) as zipped:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                zipped.write(path, output.name + "/" + str(path.relative_to(output)))
    with ZipFile(temporary) as zipped:
        assert zipped.testzip() is None
    temporary.replace(archive)
    digest = sha(archive)
    archive.with_suffix(".zip.sha256").write_text(f"{digest}  {archive.name}\n")
    print(
        json.dumps({"archive": str(archive), "bytes": archive.stat().st_size, "sha256": digest}),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    finalize(args.base, args.output)
