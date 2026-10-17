"""Freeze and package the validated administrative-geography graph version."""

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from extend_uk_geography import BASE, OUTPUT
from prepare_uk_financials import sha, write_json
from prepare_uk_graph import ROOT


def finalize(base, output):
    validation = json.loads((output / "validation.json").read_text())
    if not validation["passed"]:
        raise ValueError("Independent validation must pass before packaging")
    for name, digest in validation["validatedSha256"].items():
        if sha(output / name) != digest:
            raise ValueError("Validated file changed: " + name)
    summary = json.loads((output / "geography-summary.json").read_text())
    paths = [
        ROOT / "scripts" / name
        for name in (
            "fetch_uk_postcode_geography.py",
            "extend_uk_geography.py",
            "validate_uk_geography.py",
            "finalize_uk_geography.py",
            "uk_graph/geography.py",
            "tests/test_uk_geography.py",
        )
    ]
    for path in paths:
        target = output / "code" / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    shutil.copyfile(
        ROOT / "docs/architecture/uk-research-geography.md", output / "uk-research-geography.md"
    )
    (output / "README.md").write_text(
        f"""# 企业研究图 v4：行政地区与行业×地区超边

保留全部 {summary["researchCompanies"]:,} 家研究企业、58 家母公司、155 条并表关系、
全部财务、标签、事件及原有 13,229 个超边，不改工作台。

新增 {summary["newGroups"]:,} 个超边、{summary["newMemberships"]:,} 条成员关联；
合计 {summary["groups"]:,} 个超边、{summary["memberships"]:,} 条成员关联。
新增类型为行政地方当局、英格兰大区，以及两位/五位 SIC 分别与这两类行政地区的交叉群组。
使用群组节点和成员关联，不生成企业两两连接。各类型数量见 `hyperedge-type-summary.csv`。

## 来源与时点

行政区代码来自 ONSPD August 2026，名称来自 ONS May 2026 英国行政区关联表；
原始响应、字段元数据、来源 URL、版本和摘要保存在 `sources/ons-geography/`。
静态图使用 2026-09-30 企业登记邮编；按用户接受的粗略假设，允许近似历史观察。
这不是已核实的历史注册地址或历史行政边界，`historical_prediction_eligible` 仍为 False。
英格兰大区只适用于英格兰；其他地区的伪大区代码不建组，英国地方行政区均按官方代码匹配。
登记地址表示注册地，不等同于经营地。未匹配、歧义、缺失及单成员候选不造组，企业全部保留。

## 文件与关联

- `nodes.csv`、`edges.csv`：企业及并表关系，原样保留；不良事件仍是观察标签。
- `groups.csv`、`group-memberships.csv`：完整超边及成员。
- `group-components.csv`：行业×地区超边的两个组成群组，不表示所有权。
- `membership-evidence.csv`、`company-geography-evidence.jsonl.gz`：逐成员来源。
  包含登记原行、SIC、邮编目录原响应及摘要。
- `enterprise-and-hyperedges.graphml`：全部企业、群组和关联的完整导出；企业专用 GraphML 也保留。
- `observation-geography.csv`：209,192 条观察的地区侧表，以 `sample_id` 关联财务。
  优先使用已有历史财报邮编，检查邮编启用/停用月份；无法使用时回退到当前登记假设。
  所有映射都使用固定 2026 区划，历史地址与边界核实标志始终为 False。
  该表不改变静态图成员，也不声称已经形成按观察时点重建的历史图。
- `geography-summary.json`、`validation.json`：覆盖、保留证明及独立核验。
- `provenance/v3/`：上一版元数据，当前数量以根目录清单为准。

## 多期财务继续使用

独立扩展 `uk-financial-history-20261017-v1` 全部保留，使用其 `features.csv` 获取上期和趋势；
按 `sample_id` 关联地区侧表、按 `company_id` 关联本图。
扩展 ZIP SHA256：29c98dd6e004ec9fdab86bb88618529430fd8593b42fc596c52984b6aeee5e00。
本包的 `features.csv` 保留 v3 原列，未重复装入独立多期扩展及约 20 GB 解压财报。
原件包与原始缓存继续复用，未删除任何企业或原财报。

目录仅提取本研究所需邮编，原始公开查询完整缓存；不是删除研究企业。
具体时点规则、复现命令及不足见 `uk-research-geography.md`。
""",
        encoding="utf-8",
    )
    files = {
        str(path.relative_to(output)): {"bytes": path.stat().st_size, "sha256": sha(path)}
        for path in sorted(output.rglob("*"))
        if path.is_file() and path.relative_to(output).as_posix() != "delivery-manifest.json"
    }
    base_manifest = json.loads((base / "delivery-manifest.json").read_text())
    write_json(
        output / "delivery-manifest.json",
        {
            "format": "uk-research-geography-v4-delivery",
            "validated": True,
            "gitCommit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "baseDirectory": base.name,
            "baseDeliverySha256": sha(base / "delivery-manifest.json"),
            "sourceFinancialBundlesRetained": base_manifest["sourceFinancialBundlesRetained"],
            "financialHistoryExtension": summary["financialHistoryExtension"],
            "researchAssumption": summary["researchAssumption"],
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
    print(json.dumps({"archive": str(archive), "bytes": archive.stat().st_size, "sha256": digest}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=BASE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    finalize(args.base, args.output)
