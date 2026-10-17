"""Publish an immutable research graph with adverse events confined to supervision."""

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]

REMOVED = {"events.csv", "event-node-links.csv", "out-of-scope-events.csv"}
NS = "{http://graphml.graphdrawing.org/xmlns}"


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def clean_node(row, names):
    result = {k: v for k, v in row.items() if not k.startswith("event_")}
    if row.get("name_source") == "event_record_reference":
        name = names.get(row["id"], "")
        result.update(
            name=name or row["id"],
            name_source="selected_historical_report" if name else "company_id_fallback",
            name_source_date="",
            name_missing=str(not bool(name)),
        )
    return result


def rewrite_graphml(source, target, nodes):
    # The frozen exporter writes one complete node per line; parse every rewritten line.
    with source.open() as left, target.open("w") as right:
        for line in left:
            if line.startswith("<key ") and 'id="event_' in line:
                continue
            if not line.startswith("<node "):
                right.write(line)
                continue
            element = ET.fromstring(line)
            node = nodes.get(element.attrib["id"])
            for child in list(element):
                field = child.attrib["key"]
                if field.startswith("event_"):
                    element.remove(child)
                elif node is not None and field in node:
                    child.text = str(node[field])
            right.write(ET.tostring(element, encoding="unicode") + "\n")


def graph_identity(path):
    nodes, edges = set(), hashlib.sha256()
    count = 0
    for _, element in ET.iterparse(path, events=("end",)):
        kind = element.tag.rsplit("}", 1)[-1]
        if kind == "node":
            identity = element.attrib["id"]
            assert identity not in nodes
            nodes.add(identity)
            element.clear()
        elif kind == "edge":
            payload = [element.attrib, [(c.attrib, c.text) for c in element]]
            edges.update(json.dumps(payload, sort_keys=True).encode())
            count += 1
            element.clear()
    return nodes, count, edges.hexdigest()


def validate(base, output):
    manifest = json.loads((output / "graph-manifest.json").read_text())
    assert "eventJoin" not in manifest
    assert all(not (output / name).exists() for name in REMOVED)
    current = {r["id"]: r for r in read_csv(output / "nodes.csv")}
    old = {r["id"]: r for r in read_csv(base / "nodes.csv")}
    assert current.keys() == old.keys()
    assert all(not any(k.startswith("event_") for k in r) for r in current.values())
    assert all(r["name_source"] != "event_record_reference" for r in current.values())
    for identity, row in current.items():
        for key, value in row.items():
            if key not in {"name", "name_source", "name_source_date", "name_missing"}:
                assert value == old[identity][key]
    preserved = {}
    for name in (
        "labels.csv", "features.csv", "matches.csv", "excluded-cases.csv",
        "excluded-case-basic-information.csv", "node-observations.csv", "edges.csv",
        "groups.csv", "group-memberships.csv", "membership-evidence.csv",
    ):
        assert sha(base / name) == sha(output / name), name
        preserved[name] = sha(output / name)
    graph_counts = {}
    for source in sorted(base.glob("*.graphml")):
        before = graph_identity(source)
        after = graph_identity(output / source.name)
        assert before == after, source.name
        for _, element in ET.iterparse(output / source.name, events=("end",)):
            kind = element.tag.rsplit("}", 1)[-1]
            if kind == "key":
                assert not element.attrib["id"].startswith("event_")
            elif kind == "node":
                data = {c.attrib["key"]: c.text or "" for c in element}
                assert not any(k.startswith("event_") for k in data)
                assert data.get("name_source") != "event_record_reference"
                if element.attrib["id"] in current:
                    assert data == current[element.attrib["id"]]
                element.clear()
            elif kind == "edge":
                element.clear()
        graph_counts[source.name] = {"nodes": len(after[0]), "edges": after[1]}
    return {
        "passed": True, "companyNodes": len(current), "graphs": graph_counts,
        "eventsInGraph": False, "labelsByteIdentical": True,
        "graphTopologyUnchanged": True, "preservedSha256": preserved,
        "eventSourcedNamesReplaced": sum(
            r["name_source"] == "event_record_reference" for r in old.values()
        ),
    }


def run(base, output):
    if output.exists() or base.resolve() in output.resolve().parents:
        raise ValueError("Choose a new output outside the immutable base dataset")
    base_delivery = json.loads((base / "delivery-manifest.json").read_text())
    for name, record in base_delivery["files"].items():
        if sha(base / name) != record["sha256"]:
            raise ValueError("Base delivery digest mismatch: " + name)
    output.mkdir(parents=True)
    replaced = {
        "README.md", "graph-manifest.json", "full-graph-export.json", "nodes.csv",
        "delivery-manifest.json", "validation.json", "graph-summary.json",
    }
    for path in base.iterdir():
        if path.name in REMOVED | replaced or path.suffix == ".graphml":
            continue
        if path.is_dir():
            shutil.copytree(path, output / path.name)
        else:
            shutil.copyfile(path, output / path.name)
    names = {}
    for filename in ("features.csv", "excluded-case-basic-information.csv"):
        for row in read_csv(base / filename):
            if row.get("historical_registered_name"):
                names.setdefault(row["company_id"], row["historical_registered_name"])
    nodes = {r["id"]: clean_node(r, names) for r in read_csv(base / "nodes.csv")}
    write_csv(output / "nodes.csv", nodes.values(), list(next(iter(nodes.values()))))
    for path in sorted(base.glob("*.graphml")):
        rewrite_graphml(path, output / path.name, nodes)
    manifest = json.loads((base / "graph-manifest.json").read_text())
    manifest.pop("eventJoin", None)
    manifest.update(
        format="uk-research-graph-labels-only-v1", parentVersion=base.name,
        supervision={"labels": "labels.csv", "joinKey": "sample_id",
                     "observationJoin": "node-observations.csv", "eventsInGraph": False,
                     "rawEventEvidence": "../uk-adverse-events-2020-2025-v1"},
    )
    write_json(output / "graph-manifest.json", manifest)
    summary = json.loads((base / "graph-summary.json").read_text())
    summary.update(eventsInGraph=False, namesMissing=sum(
        r["name_missing"] == "True" for r in nodes.values()
    ))
    write_json(output / "graph-summary.json", summary)
    full = json.loads((base / "full-graph-export.json").read_text())
    full["sha256"] = sha(output / full["file"])
    write_json(output / "full-graph-export.json", full)
    (output / "README.md").write_text(
        "# 英国研究图谱：不良事件仅作标签\n\n"
        "图谱仅包含企业、并表关系、属性群组及成员关联。不良事件不作为节点、边或群组，"
        "不导出 events.csv、event-node-links.csv、out-of-scope-events.csv，清单无 eventJoin。\n\n"
        "移除节点及全部 GraphML 的 event_reference_sic2007；事件来源名称改用已有历史财报"
        "名称，缺失则展示企业编号。全部企业 ID、关系和群组成员保持不变。\n\n"
        "labels.csv 按 sample_id 保存观察级监督标签；node-observations.csv 关联企业与观察。"
        "财务、标签、配对和排除清单原字节保留，不将标签写入节点或用于造边。\n\n"
        "原始事件证据仍在独立 uk-adverse-events-2020-2025-v1 包和旧版本，"
        "company-reference.csv 中的 event_reference_* 只作历史来源审计，不是图特征。"
        "旧版 code、base-* 及 provenance 为复现档案，以本版 graph-manifest.json 为准。\n\n"
        "当前登记近似历史观察的既有研究假设继续保留，不声称验证了历史关系。"
        "独立多期财务扩展继续按 sample_id/company_id 关联。\n",
        encoding="utf-8",
    )
    code = output / "code/scripts/isolate_uk_graph_labels.py"
    shutil.copyfile(__file__, code)
    result = validate(base, output)
    write_json(output / "validation.json", result)
    files = {
        str(p.relative_to(output)): {"bytes": p.stat().st_size, "sha256": sha(p)}
        for p in sorted(output.rglob("*")) if p.is_file()
    }
    write_json(output / "delivery-manifest.json", {
        "format": "uk-research-graph-labels-only-v1-delivery", "validated": True,
        "baseDirectory": base.name, "baseDeliverySha256": sha(base / "delivery-manifest.json"),
        "sourceFinancialBundlesRetained": base_delivery["sourceFinancialBundlesRetained"],
        "files": files,
    })
    archive = output.with_suffix(".zip")
    if archive.exists():
        raise ValueError("Archive already exists")
    with ZipFile(archive, "w", compression=ZIP_DEFLATED, compresslevel=6) as zipped:
        for p in sorted(output.rglob("*")):
            if p.is_file():
                zipped.write(p, output.name + "/" + str(p.relative_to(output)))
    with ZipFile(archive) as zipped:
        assert zipped.testzip() is None
    digest = sha(archive)
    archive.with_suffix(".zip.sha256").write_text(f"{digest}  {archive.name}\n")
    print(json.dumps({**result, "archive": str(archive), "sha256": digest}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=ROOT / "outputs/uk-research-graph-20261017-v3")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "outputs/uk-research-graph-20261017-labels-only-v1"
    )
    args = parser.parse_args()
    run(args.base, args.output)
