"""Consolidate validated UK graph, geography, financial history and labels in datasets."""

import argparse
import json
import shutil
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from isolate_uk_graph_labels import (
    REMOVED,
    clean_node,
    graph_identity,
    read_csv,
    rewrite_graphml,
    sha,
    write_csv,
    write_json,
)

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "datasets/archive/uk-research-20261017"


def verify_delivery(directory):
    manifest = json.loads((directory / "delivery-manifest.json").read_text())
    assert manifest["validated"] is True
    for name, item in manifest["files"].items():
        if sha(directory / name) != item["sha256"]:
            raise ValueError("Input digest mismatch: " + str(directory / name))
    return sha(directory / "delivery-manifest.json")


def verify_observations(graph, history):
    base = {r["sample_id"]: r for r in read_csv(graph / "features.csv")}
    assert sha(graph / "labels.csv") == sha(history / "labels.csv")
    count = 0
    for row in read_csv(history / "features.csv"):
        original = base.pop(row["sample_id"])
        assert all(row[k] == value for k, value in original.items())
        count += 1
    assert not base
    return count


def build(graph, history, output):
    if output.exists() or output.with_suffix(".zip").exists():
        raise ValueError("Current dataset already exists; choose a new staging destination")
    inputs = {"graph": verify_delivery(graph), "financialHistory": verify_delivery(history)}
    observations = verify_observations(graph, history)
    output.mkdir(parents=True)
    audit = output / "audit"
    metadata = {
        "README.md",
        "graph-manifest.json",
        "delivery-manifest.json",
        "validation.json",
        "graph-summary.json",
        "full-graph-export.json",
        "base-graph-manifest.json",
        "base-validation.json",
        "feature-contract.json",
        "coverage.json",
        "source-manifest.json",
        "hyperedge-manifest.json",
        "geography-manifest.json",
        "geography-summary.json",
        "quality-report.json",
        "repair-progress.json",
        "basic-information-gaps.json",
        "basic-information-gaps.csv",
    }
    for path in graph.iterdir():
        if path.name in REMOVED or path.suffix == ".graphml" or path.name == "nodes.csv":
            continue
        historical = (
            path.name in metadata
            or path.suffix == ".md"
            or path.name
            in {
                "code",
                "provenance",
                "features.csv",
                "labels.csv",
            }
        )
        target = audit / "graph" / path.name if historical else output / path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.is_dir():
            shutil.copytree(path, target)
        else:
            shutil.copyfile(path, target)
    # The authoritative current features include all baseline columns and financial trends.
    for path in history.iterdir():
        if path.name == "sources":
            shutil.copytree(path, output / "sources", dirs_exist_ok=True)
        elif path.name in {
            "features.csv",
            "labels.csv",
            "feature-contract.json",
            "financial-history.csv",
            "financial-report-sources.csv",
            "sample-history-links.csv",
            "trend-coverage.csv",
            "history-facts.jsonl.gz",
            "history-source-facts.jsonl.gz",
            "history-quality-issues.jsonl.gz",
        }:
            shutil.copyfile(path, output / path.name)
        else:
            target = audit / "financial-history" / path.name
            target.parent.mkdir(parents=True, exist_ok=True)
            if path.is_dir():
                shutil.copytree(path, target)
            else:
                shutil.copyfile(path, target)
    names = {}
    for filename in ("features.csv", "excluded-case-basic-information.csv"):
        for row in read_csv(graph / filename):
            if row.get("historical_registered_name"):
                names.setdefault(row["company_id"], row["historical_registered_name"])
    nodes = {r["id"]: clean_node(r, names) for r in read_csv(graph / "nodes.csv")}
    write_csv(output / "nodes.csv", nodes.values(), list(next(iter(nodes.values()))))
    graph_checks = {}
    for path in sorted(graph.glob("*.graphml")):
        rewrite_graphml(path, output / path.name, nodes)
        before, after = graph_identity(path), graph_identity(output / path.name)
        assert before == after
        graph_checks[path.name] = {"nodes": len(after[0]), "edges": after[1]}
    manifest = json.loads((graph / "graph-manifest.json").read_text())
    for key in ("eventJoin", "inputFiles", "codeFiles", "parentVersion"):
        manifest.pop(key, None)
    manifest.update(format="uk-research-unified-graph-v1", eventsInGraph=False)
    write_json(output / "graph-manifest.json", manifest)
    full = json.loads((graph / "full-graph-export.json").read_text())
    full["sha256"] = sha(output / full["file"])
    write_json(output / "full-graph-export.json", full)
    for name in ("labels.csv", "features.csv", "feature-contract.json"):
        assert sha(output / name) == sha(history / name)
    for name in (
        "edges.csv",
        "groups.csv",
        "group-memberships.csv",
        "membership-evidence.csv",
        "node-observations.csv",
        "observation-geography.csv",
        "group-components.csv",
    ):
        assert sha(output / name) == sha(graph / name)
    assert all(not (output / name).exists() for name in REMOVED)
    assert all(not any(k.startswith("event_") for k in r) for r in nodes.values())
    assert all(r["name_source"] != "event_record_reference" for r in nodes.values())
    geo_ids = {r["sample_id"] for r in read_csv(output / "observation-geography.csv")}
    sample_ids = {r["sample_id"] for r in read_csv(output / "features.csv")}
    assert geo_ids == sample_ids
    write_json(
        output / "validation.json",
        {
            "passed": True,
            "observations": observations,
            "companyNodes": len(nodes),
            "graphs": graph_checks,
            "baselineFeatureColumnsPreserved": True,
            "financialTrendFeaturesIncluded": True,
            "labelsByteIdentical": True,
            "geographySamplesComplete": True,
            "eventsInGraph": False,
            "namesUsingCompanyId": sum(r["name_missing"] == "True" for r in nodes.values()),
        },
    )
    write_json(
        output / "dataset.json",
        {
            "format": "uk-research-dataset-v1",
            "features": "features.csv",
            "labels": "labels.csv",
            "featureContract": "feature-contract.json",
            "sampleKey": "sample_id",
            "companyKey": "company_id",
            "graph": "graph-manifest.json",
            "observationJoin": "node-observations.csv",
            "geography": "observation-geography.csv",
            "financialHistory": "financial-history.csv",
            "historyJoin": "sample-history-links.csv",
            "eventsAreSupervisionOnly": True,
            "upstreamDeliverySha256": inputs,
            "currentRegistryApproximatesHistory": True,
            "historicallyVerified": False,
            "rawSourceRoot": "../sources",
            "historicalDeliveries": "../archive/uk-research-20261017",
        },
    )
    (output / "README.md").write_text(
        "# 英国研究数据集（当前完整版本）\n\n"
        "以后统一使用本目录，无需拼接旧图谱、财务扩展或地区扩展包。\n\n"
        "- features.csv：209192条观察的完整财务、历史基本信息和多期趋势。\n"
        "- labels.csv：按sample_id关联的观察级不良标签，原标签字节不变。\n"
        "- nodes.csv、edges.csv：全部企业及并表关系，不含事件属性。\n"
        "- groups.csv、group-memberships.csv：包含行政地区和行业×地区的50226个群组。\n"
        "- enterprise-and-hyperedges.graphml：完整企业、超边及成员关联。\n"
        "- node-observations.csv：企业ID与观察ID关联。\n"
        "- observation-geography.csv：全部观察的行政地区侧表。\n"
        "- financial-history.csv、sample-history-links.csv：多期事实和版本关联。\n"
        "- feature-contract.json：可编码特征清单；dataset.json：统一机器入口。\n"
        "- sources/及逐行证据：本包专用来源，基础原件缓存统一在../sources/。\n"
        "- audit/：历史说明、上游清单和验证，不能当作当前特征或标签入口。\n\n"
        "事件仅用于标签；不导出事件关联边或节点。事件源仍在../sources/和归档包。"
        "company-reference.csv中的event_reference列仅作来源审计，不是图特征。\n\n"
        "当前登记近似历史观察的研究假设保持，尚未核实历史地址/关系与精确申报日。"
        "14211家不再使用事件来源名称而显示企业编号，企业全部保留。\n",
        encoding="utf-8",
    )
    code = output / "code"
    code.mkdir()
    for filename in ("consolidate_uk_research.py", "isolate_uk_graph_labels.py"):
        shutil.copyfile(Path(__file__).with_name(filename), code / filename)
    files = {
        str(p.relative_to(output)): {"bytes": p.stat().st_size, "sha256": sha(p)}
        for p in sorted(output.rglob("*"))
        if p.is_file()
    }
    write_json(
        output / "delivery-manifest.json",
        {
            "format": "uk-research-unified-delivery-v1",
            "validated": True,
            "files": files,
            "upstreamDeliverySha256": inputs,
        },
    )
    archive = output.with_suffix(".zip")
    with ZipFile(archive, "w", compression=ZIP_DEFLATED, compresslevel=6) as zipped:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                zipped.write(path, output.name + "/" + str(path.relative_to(output)))
    with ZipFile(archive) as zipped:
        assert zipped.testzip() is None
    digest = sha(archive)
    archive.with_suffix(".zip.sha256").write_text(f"{digest}  {archive.name}\n")
    print(json.dumps({"dataset": str(output), "archive": str(archive), "sha256": digest}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, default=ARCHIVE / "uk-research-graph-20261017-v4")
    parser.add_argument(
        "--history", type=Path, default=ARCHIVE / "uk-financial-history-20261017-v1"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "datasets/uk_research")
    args = parser.parse_args()
    build(args.graph, args.history, args.output)
