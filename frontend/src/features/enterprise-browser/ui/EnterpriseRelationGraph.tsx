import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { ResponseEnterpriseCompany } from "@/shared/api/generated/schema";
import { GraphView } from "@/shared/ui/graph";
import { chartPalette } from "@/shared/config/theme/palette";
import Card from "@/shared/ui/Card";
import { type EnterpriseRelationRecord, buildRelationGraph, companyGraphId, GRAPH_NODE_LIMIT, GROUP_MEMBER_LIMIT, relationLabel, relationType } from "../lib/relationGraph";

export function EnterpriseRelationGraph({ data }: { data: ResponseEnterpriseCompany }) {
  const [filter, setFilter] = useState("all");
  const [selected, setSelected] = useState<string | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<string | null>(null);
  const graph = useMemo(() => buildRelationGraph(data, filter), [data, filter]);
  const nodes = useMemo(() => graph.nodes.map(node => ({ ...node, color: graph.groups.has(node.id) ? chartPalette.accent : chartPalette.primary })), [graph]);
  const records = [...(data.related.edge?.items ?? []), ...(data.related.hyperedge?.items ?? [])];
  const types = [...new Set(records.map(relationType))];
  const selectedCompany = selected ? graph.companies.get(selected) : undefined;
  const record = (selectedEdge ? graph.evidence.get(selectedEdge) : undefined) ?? (selected ? graph.groups.get(selected) : undefined);
  const evidenceOptions = [...new Map([...graph.evidence].map(([id, item]) => [item.sequence, { id, item }])).values()];
  function selectEvidence(id: string) {
    const item = graph.evidence.get(id);
    setSelectedEdge(evidenceOptions.find(option => option.item.sequence === item?.sequence)?.id ?? null);
    setSelected(null);
  }
  const ordinary = data.related.edge;
  const grouped = data.related.hyperedge;
  const hasRelations = (ordinary?.total ?? 0) + (grouped?.total ?? 0) > 0;
  function selectNode(id: string | null) { setSelected(id); setSelectedEdge(null); }
  return <div id="enterprise-graph" className="scroll-mt-6"><Card title="企业关系图谱" subtitle={`来源：${data.dataset.name} · 快照：${data.company.snapshot} · 当前企业的局部关系`} icon="ri-share-line" bodyClassName="space-y-4 p-5">
    {!hasRelations ? <p className="text-sm text-foreground-500">本数据集尚未保存与该企业关联的关系或群组。请在数据准备案例中补充图 JSON，核验并确认导入后查看。<Link className="ml-2 text-primary-500 underline" to={data.provenance?.preparationId ? `/data-prep?preparation=${encodeURIComponent(data.provenance.preparationId)}` : "/data-prep"}>补充关系数据 →</Link></p> : <>
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs"><p>企业节点 · 蓝色　群组节点 · 金色　有向实线 · 原始关系　无向虚线 · 群组成员</p><label>关系类型 <select aria-label="筛选图谱关系类型" className="ml-2 rounded border border-background-300 bg-background-50 p-2" value={filter} onChange={event => { setFilter(event.target.value); selectNode(null); }}><option value="all">全部类型</option>{types.map(type => <option key={type} value={type}>{relationLabel(type)}</option>)}</select></label></div>
      <p className="text-xs leading-6 text-foreground-500">已加载普通关系 {ordinary?.items.length ?? 0}/{ordinary?.total ?? 0} 条、群组 {grouped?.items.length ?? 0}/{grouped?.total ?? 0} 组（接口每类最多20条）。画布最多 {GRAPH_NODE_LIMIT} 个节点，每组最多展开 {GROUP_MEMBER_LIMIT} 家企业；当前显示 {graph.companies.size} 家企业、{graph.groups.size} 个群组。{graph.omittedMembers > 0 ? `未展开群组成员共 ${graph.omittedMembers} 个成员位置，同企业可出现在不同组。` : ""}{graph.omittedRecords > 0 ? `另有 ${graph.omittedRecords} 条关系/群组因画布上限未展示。` : ""}群组连接仅表示共同成员身份，不代表股权或风险传导。</p>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_260px]">
        <GraphView nodes={nodes} edges={graph.edges} centerId={graph.centerId} selectedId={selected} onSelect={selectNode} onSelectEdge={selectEvidence} height={480} ariaLabel="已导入企业局部关系图谱" />
        <aside className="space-y-4 rounded-lg border border-background-200 p-4 text-xs" aria-label="图谱选择与来源">
          <label className="block">选择企业或群组<select aria-label="选择图谱节点" className="mt-2 w-full rounded border border-background-300 bg-background-50 p-2" value={selected ?? ""} onChange={event => selectNode(event.target.value || null)}><option value="">点击图中节点查看</option>{graph.nodes.map(node => <option key={node.id} value={node.id}>{node.label}</option>)}</select></label>
          <label className="block">查看关系依据<select aria-label="选择图谱关系依据" className="mt-2 w-full rounded border border-background-300 bg-background-50 p-2" value={selectedEdge ?? ""} onChange={event => selectEvidence(event.target.value)}><option value="">点击连线查看来源</option>{evidenceOptions.map(({ id, item }) => <option key={id} value={id}>{relationLabel(relationType(item))} · {item.source ? `${item.source} → ${item.target}` : `${item.members.length}家企业`}</option>)}</select></label>
          {selectedCompany && <div className="space-y-3"><p className="break-all font-medium">企业：{selectedCompany}</p><Link className="inline-block text-primary-500 underline" to={`/company/${encodeURIComponent(data.dataset.id)}/${encodeURIComponent(selectedCompany)}?source=uploaded#enterprise-graph`}>{companyGraphId(data.company.nodeId!) === selected ? "当前企业详情" : "打开该企业详情与相邻关系 →"}</Link></div>}
          {record && <RelationEvidence record={record} />}
          {!selectedCompany && !record && <p className="leading-6 text-foreground-500">点击企业查看详情入口；点击群组或连线查看原始关系和来源。也可以使用上方选择框。</p>}
        </aside>
      </div>
    </>}
  </Card></div>;
}

function RelationEvidence({ record }: { record: EnterpriseRelationRecord }) {
  const raw = record.data.sourceRecord;
  const source = raw && typeof raw === "object" && !Array.isArray(raw) ? raw as Record<string, unknown> : undefined;
  return <div className="space-y-2 break-words leading-6"><p className="font-semibold">{relationLabel(relationType(record))} · 记录 {record.sequence}</p>{record.kind === "edge" ? <><p>{record.source} → {record.target}</p><p>证据权重：{record.data.weight == null ? "来源未提供" : String(record.data.weight)}（不解释为持股比例或概率）</p></> : <p>原始群组共有 {record.members.length} 家企业；实际展开范围以画布上方统计为准。</p>}<p>快照：{record.snapshot}</p>{source ? <><p>来源文件：{String(source.filename ?? "未提供")}</p><p>数组位置：{String(source.path ?? "未提供")}</p><p className="break-all">文件 SHA-256：{String(source.sha256 ?? "未提供")}</p></> : <p className="text-foreground-500">该关系未提供逐条文件追溯信息，保留的数据集记录可在下方核对。</p>}</div>;
}
