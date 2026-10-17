"""Validate, document and package the repaired independent UK research dataset."""

import argparse
import json
import shutil
import subprocess
from collections import Counter
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from prepare_uk_basic_information import read_csv
from prepare_uk_financials import sha, write_csv, write_json
from uk_financials.basic import parser_signature as basic_signature
from uk_financials.facts import parser_signature as financial_signature
from validate_uk_research_repairs import validate

ROOT = Path(__file__).resolve().parents[1]


def finalize(base, output):
    report = json.loads((output / "quality-report.json").read_text())
    provenance = output / "provenance/v2"
    for name in [
        "hyperedge-manifest.json",
        "source-manifest.json",
        "feature-contract.json",
        "uk-research-hyperedges.md",
    ]:
        if not (provenance / name).exists() and (output / name).exists():
            shutil.copyfile(output / name, provenance / name)
    if (output / "uk-research-hyperedges.md").exists():
        (output / "uk-research-hyperedges.md").unlink()
    manifest = json.loads((provenance / "hyperedge-manifest.json").read_text())
    manifest["preservedFiles"] = {
        name: digest
        for name, digest in manifest["preservedFiles"].items()
        if name not in {"source-manifest.json", "feature-contract.json"}
        and (output / name).is_file() and sha(output / name) == digest
    }
    manifest["inheritedGraphConstructionManifest"] = "provenance/v2/hyperedge-manifest.json"
    manifest["qualityRevision"] = "v3; financial and country fields repaired, graph unchanged"
    write_json(output / "hyperedge-manifest.json", manifest)
    source = json.loads((provenance / "source-manifest.json").read_text())
    source["originalBasicParserSha256"] = source.pop("parserSha256")
    source["originalBasicPipelineSha256"] = source.pop("pipelineSha256")
    source.update(
        parserSha256=basic_signature(),
        financialParserSha256=financial_signature(),
        repairPipelineSha256=sha(ROOT / "scripts/repair_uk_research_data.py"),
    )
    write_json(output / "source-manifest.json", source)
    contract = json.loads((provenance / "feature-contract.json").read_text())
    contract["categoricalFeatureAllowlist"] = list(
        dict.fromkeys(
            contract["categoricalFeatureAllowlist"]
            + ["historical_country_of_incorporation_jurisdiction"]
        )
    )
    contract.update(
        countryRepresentation="ISO country code plus separate registry jurisdiction",
        qualityAuditFieldsAreNotModelFeatures=True,
        currentReferenceUseAllowedUnderUserAssumption=True,
        researchAssumption=report["researchAssumption"],
    )
    write_json(output / "feature-contract.json", contract)
    country_counts, countries, quarantine_rows = Counter(), Counter(), Counter()
    for row in read_csv(output / "features.csv"):
        country_counts[
            (
                row["historical_country_of_incorporation_raw"],
                row["historical_country_of_incorporation"],
                row["historical_country_of_incorporation_normalization_status"],
            )
        ] += 1
        countries[row["historical_country_of_incorporation"] or "missing"] += 1
        for metric in filter(None, row["financial_quarantined_metrics"].split("|")):
            quarantine_rows[metric] += 1
    write_csv(
        output / "country-normalization-summary.csv",
        [
            {
                "raw_value": key[0],
                "country_code": key[1],
                "status": key[2],
                "observation_rows": count,
            }
            for key, count in sorted(country_counts.items())
        ],
        ["raw_value", "country_code", "status", "observation_rows"],
    )
    report.update(
        normalizedCountryObservationCounts=countries, quarantinedObservationMetrics=quarantine_rows
    )
    write_json(output / "quality-report.json", report)
    doc = ROOT / "docs/architecture/uk-research-data-quality.md"
    shutil.copyfile(doc, output / doc.name)
    for path in [
        ROOT / "scripts/repair_uk_research_data.py",
        ROOT / "scripts/validate_uk_research_repairs.py",
        ROOT / "scripts/finalize_uk_research_repairs.py",
        ROOT / "scripts/prepare_uk_basic_information.py",
        ROOT / "scripts/prepare_uk_financials.py",
        ROOT / "scripts/prepare_uk_controls.py",
        *sorted((ROOT / "scripts/uk_financials").glob("*.py")),
        ROOT / "scripts/tests/test_uk_basic_information.py",
        ROOT / "scripts/tests/test_uk_financials.py",
    ]:
        destination = output / "code" / path.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
    validation = validate(base, output)
    changed = report["changes"]
    (output / "README.md").write_text(
        f"""# 独立企业研究数据集 v3：金额回补、字段质量与国家规范化

原 229,907 家研究企业、58 家母公司、155 条并表关系、13,229 个超边和全部成员关联保持不变。
209,192 条观察、全部标签、事件、配对及未入组企业保持不变；不良事件不作为输入图节点。

## 本次结果

- 全量重解析 {validation["reports"]:,} 份原财报，每份核对 SHA256、大小和 CRC32。
- 原有金额观察 {validation["originalMonetaryNonmissing"]:,} 条；
  清洗回补后 {validation["repairedMonetaryNonmissing"]:,} 条。
- 从无金额恢复 {changed["monetary_missing_recovered"]:,} 条观察；
  清洗后转为无可接受金额 {changed["monetary_now_missing"]:,} 条。
- 从原始报表维度恢复的已接受事实 {report["reports"]["original_dimension_accepted_facts"]:,} 项。
- 国家代码观察分布：{json.dumps(countries, ensure_ascii=False)}。

## 文件

- `features.csv`：清洗后训练候选特征；隔离字段为空且 missing=True，企业与观察保留。
- `financial-facts.jsonl.gz`：清洗后事实。
- `financial-source-facts.jsonl.gz`：质量校验前的所选源事实。
- `financial-quality-issues.jsonl.gz`：逐报告、逐字段的原值、隔离/保留警告和原因。
- `financial-value-changes.csv`：逐观察的财务旧值、新值及变更原因。
- `historical-basic-profiles.jsonl.gz`：基本信息原事实、国家原值/规范值与标准化证据。
- `country-normalization-summary.csv`：原值到国家代码的统计，辖区单独保存。
- `company-reference.csv`：保留原始登记字段，新增国家规范列；并未把当前字段暗中填入历史特征。
- `quality-report.json` / `validation.json`：覆盖变化、质量策略、保留证明和独立校验。
- `provenance/v2/`：旧版说明、清单与验证，只用于版本溯源；当前交付以根目录 README/清单为准。
- 图文件、事件表、标签及观察关联的读取方式保持不变。
- `feature-contract.json` 明确训练候选字段，来源和质量审计字段不自动编码入模型。

## 本轮采用的研究假设

按用户明确同意，允许将当前登记属性近似用于历史观察研究。此为粗略假设，不冒称历史已核实；
`graph-manifest.json` 中保留来源时间并记录此假设。图结构未重建，标签未改变。

质量阈值是字段隔离/复核政策，不是将源值修正成某个猜测值。负净资产、负利润和合法的非负平均员工小数保留。
详细规则见 `uk-research-data-quality.md`。
原财报仍在本地缓存及原有财务源数据包中，此包不重复装入约 20 GB 的解压原件。
""",
        encoding="utf-8",
    )
    git_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    files = {
        str(path.relative_to(output)): {"bytes": path.stat().st_size, "sha256": sha(path)}
        for path in sorted(output.rglob("*"))
        if path.is_file() and path.name != "delivery-manifest.json"
    }
    # The archived v2 manifest is itself evidence and must remain in the ledger.
    archived = provenance / "delivery-manifest.json"
    files[str(archived.relative_to(output))] = {
        "bytes": archived.stat().st_size,
        "sha256": sha(archived),
    }
    base_delivery = json.loads((base / "delivery-manifest.json").read_text())
    write_json(
        output / "delivery-manifest.json",
        {
            "format": "uk-research-graph-quality-v3-delivery",
            "gitCommit": git_commit,
            "validated": True,
            "baseDirectory": str(base.resolve()),
            "baseDeliverySha256": sha(base / "delivery-manifest.json"),
            "researchAssumption": report["researchAssumption"],
            "sourceFinancialBundlesRetained": base_delivery["sourceFinancialBundlesRetained"],
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
