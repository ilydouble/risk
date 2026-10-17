import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import * as GraphApi from "@/entities/graph/api/graphApi";
import type { ResponseGetDatasetGraph } from "@/shared/api/generated/schema";
import { GraphView } from "@/shared/ui/graph";
import { chartPalette } from "@/shared/config/theme/palette";
import { handleApiError } from "@/shared/api/http";
import { graphElements, companyLink } from "../lib/datasetGraph";
import { useLang } from "@/shared/lib/useLang";

const colors = { company: chartPalette.primary, person: chartPalette.secondary,
  hyperedge: chartPalette.accent, event: chartPalette.riskHigh };

export default function DatasetGraphPanel({ datasetId, companyId, depth = 1, height = 420 }: {
  datasetId: string; companyId: string; depth?: number; height?: number;
}) {
  const { pick, lang } = useLang();
  const [data, setData] = useState<ResponseGetDatasetGraph | null>(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [edgeId, setEdgeId] = useState<string | null>(null);
  const [filter, setFilter] = useState("all");
  useEffect(() => {
    const message = (zh: string, en: string) => lang === "en" ? en : zh;
    let active = true;
    setData(null); setError(""); setSelected(null); setEdgeId(null); setFilter("all");
    GraphApi.requestGetDatasetGraph({ datasetId, companyId, depth, lang }).then(value => {
      if (active) setData(value);
    }).catch(cause => {
      if (active) setError(handleApiError(cause, {
        GRAPH_DATA_UNAVAILABLE: message("该数据集尚未导入企业关系数据。", "Enterprise data is not imported yet."),
        GRAPH_COMPANY_NOT_FOUND: message("在该数据集中找不到此企业。", "Company not found in this dataset."),
        GRAPH_QUERY_TIMEOUT: message("查询超时，请减少跳数后重试。", "Query timed out. Reduce depth and retry."),
        MODELING_RESOURCE_NOT_FOUND: message("数据集不存在或无权访问。", "Dataset missing or inaccessible."),
      }));
    });
    return () => { active = false; };
  }, [datasetId, companyId, depth, lang, retry]);
  const graph = useMemo(() => graphElements(data, filter), [data, filter]);
  const edges = useMemo(() => graph.edges.map(edge => ({ ...edge, dashed: edge.kind !== "edge" })), [graph]);
  const nodes = useMemo(() => graph.nodes.map(n => ({
    ...n, color: colors[n.kind], size: n.id === data?.rootId ? 44 : n.kind === "company" ? 30 : 24,
  })), [graph, data]);
  if (error) return <div role="alert" className="space-y-2 py-4"><p>{error}</p><button className="underline" onClick={() => setRetry(n => n + 1)}>{pick("重试", "Retry")}</button></div>;
  if (!data) return <p role="status" className="py-6 text-sm">{pick("正在加载图谱…", "Loading graph…")}</p>;
  const selectedNode = data.nodes.find(n => n.id === selected);
  const selectedEdge = data.edges.find(e => e.id === edgeId);
  const detailLink = selectedNode ? companyLink(data, selectedNode) : null;
  const evidence = selectedEdge ?? selectedNode;
  const labels = { company: pick("企业", "Company"), person: pick("人物", "Person"), hyperedge: pick("群组", "Group"), event: pick("事件", "Event") };
  const reasons: Record<string, string> = {
    node_limit: pick("节点上限", "node limit"), edge_limit: pick("连线上限", "edge limit"),
    record_limit: pick("关系记录上限", "record limit"), member_limit: pick("群组成员上限", "group member limit"),
  };
  function selectNode(id: string | null) { setSelected(id); setEdgeId(null); }
  return <div className="space-y-3">
    <p className="text-xs text-foreground-500">{data.datasetName} · {pick("快照", "Snapshot")} {data.snapshot} · {pick(`${nodes.length} 个节点、${edges.length} 条连线`, `${nodes.length} nodes, ${edges.length} links`)}</p>
    <p className="text-xs text-foreground-500">{pick("企业 · 蓝色　人物 · 灰色　群组 · 金色　事件 · 红色；群组连接仅表示成员关系。", "Company · blue; person · gray; group · gold; event · red. Group links represent membership only.")}</p>
    <label className="block text-xs">{pick("关系类型", "Relation type")} <select aria-label={pick("筛选图谱关系类型", "Filter relation type")} className="rounded border border-background-300 bg-background-50 p-1" value={filter} onChange={e => { setFilter(e.target.value); selectNode(null); }}>
      <option value="all">{pick("全部", "All")}</option>{[...new Set(data.edges.map(e => e.label))].map(label => <option key={label} value={label}>{label}</option>)}
    </select></label>
    {data.truncated && <p role="status" className="text-xs text-amber-600">{pick("局部图已截断：", "Graph truncated: ")}{data.truncationReasons.map(r => reasons[r] ?? r).join(" / ")}。{pick(`群组未展开成员位置 ${data.omittedMembers} 个（不同组可能重复）。`, `${data.omittedMembers} group member positions omitted (may overlap).`)}</p>}
    <GraphView nodes={nodes} edges={edges} centerId={data.rootId} selectedId={selected}
      onSelect={selectNode} onSelectEdge={id => { setEdgeId(id); setSelected(null); }} height={height}
      ariaLabel={pick("数据集企业局部图谱", "Dataset enterprise graph")} />
    {!data.edges.length && <p className="text-sm text-foreground-500">{pick("此快照未保存与该企业关联的关系、群组或事件。", "No relationships, groups or events for this company in this snapshot.")}</p>}
    <label className="block text-xs">{pick("查看节点", "Inspect node")} <select aria-label={pick("选择图谱节点", "Select graph node")} className="max-w-full rounded border border-background-300 bg-background-50 p-1" value={selected ?? ""} onChange={e => selectNode(e.target.value || null)}><option value="">{pick("点击节点查看详情", "Select a node")}</option>{nodes.map(n => <option key={n.id} value={n.id}>{labels[n.kind]} · {n.label}</option>)}</select></label>
    {evidence && <div className="space-y-2 rounded-lg bg-background-100 p-3 text-xs">
      <p className="font-medium">{selectedNode ? labels[selectedNode.kind] : pick("关系", "Relation")} · {evidence.label}</p>
      <p>{pick("快照", "Snapshot")} {data.snapshot} · {pick("记录", "Record")} {evidence.recordSequence ?? "—"}</p>
      {selectedEdge && <p className="break-all">{selectedEdge.source} → {selectedEdge.target}</p>}
      <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-all">{JSON.stringify(evidence.data, null, 2)}</pre>
      {detailLink && <Link className="text-primary-500 underline" to={detailLink}>{pick("查看企业详情", "Company details")}</Link>}
    </div>}
    <p className="text-xs leading-5 text-foreground-500">{pick("这是数据集来源关系，可能不同于模型实际使用的训练子图；连线不代表预测贡献或风险传导。", "Source relationships may differ from the trained model subgraph; links are not prediction contributions or risk propagation.")}</p>
  </div>;
}
