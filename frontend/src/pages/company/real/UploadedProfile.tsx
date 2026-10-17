import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { requestEnterpriseCompany } from "@/entities/modeling/api/modelingApi";
import { displayEnterpriseValue, enterpriseName } from "@/entities/modeling/lib/enterpriseDisplay";
import type { ResponseEnterpriseCompany } from "@/shared/api/generated/schema";
import { handleApiError } from "@/shared/api/http";
import { EnterpriseRelationGraph } from "@/features/enterprise-browser/ui/EnterpriseRelationGraph";
import Card from "@/shared/ui/Card";
import { EnterpriseProperties } from "./EnterpriseProperties";
import { EnterpriseSourceTrace } from "./EnterpriseSourceTrace";
import { EnterpriseRiskPanel } from "./EnterpriseRiskPanel";

export default function UploadedProfile() {
  const { datasetId = "", companyId = "" } = useParams();
  const [params] = useSearchParams();
  const modelId = params.get("model") ?? "";
  const [data, setData] = useState<ResponseEnterpriseCompany>();
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    setData(undefined); setError("");
    requestEnterpriseCompany({ datasetId, companyId, modelId: modelId || undefined }).then((result) => { if (active) setData(result); }).catch((cause) => {
      if (active) setError(handleApiError(cause, { MODELING_COMPANY_NOT_FOUND: "当前数据集中没有此企业。" }));
    });
    return () => { active = false; };
  }, [datasetId, companyId, modelId, revision]);
  const back = `/search?source=uploaded&dataset=${encodeURIComponent(datasetId)}${modelId ? `&model=${encodeURIComponent(modelId)}` : ""}`;
  return <div className="space-y-5">
    <div className="flex items-center justify-between"><h1 className="text-2xl font-semibold">企业详情</h1><Link to={back} className="text-xs text-primary-400">← 返回本数据集检索</Link></div>
    {error && <p role="alert" className="rounded-lg border border-danger-500/30 p-4 text-sm text-danger-500">{error}</p>}
    {!data && !error && <p role="status" className="text-sm text-foreground-500">正在加载企业详情…</p>}
    {data && <>
      <section className="rounded-lg border border-background-200 bg-background-100 p-5"><h2 className="text-xl font-semibold">{enterpriseName(data.company)}</h2><p className="mt-2 break-all font-mono text-xs text-foreground-500">{companyId}</p><p className="mt-3 text-sm text-foreground-500">数据集：{data.dataset.name} · 快照：{data.company.snapshot} · 已有标签：{displayEnterpriseValue(data.company.data.label)}</p><Link className="mt-3 inline-block text-xs text-primary-400" to={`/?source=uploaded&dataset=${encodeURIComponent(datasetId)}`}>查看本数据集总览 →</Link></section>
      <EnterpriseRelationGraph key={`${datasetId}:${companyId}`} data={data} />
      <EnterpriseProperties data={data.company.data} />
      <EnterpriseSourceTrace provenance={data.provenance} />
      <EnterpriseRiskPanel key={`${datasetId}:${companyId}`} data={data} modelId={modelId} onUpdated={() => setRevision(value => value + 1)} />
      {Object.entries(data.related).map(([kind, related]) => <Card key={kind} title={`${({ edge: "普通关系", hyperedge: "超边", event: "事件" } as Record<string, string>)[kind] ?? kind} · ${related.total.toLocaleString()} 条`} subtitle={`仅展示同快照中与该企业相关的前${related.items.length}条记录。`} icon="ri-share-line" bodyClassName="space-y-3 p-4">
        {related.items.map((record) => <div key={record.sequence} className="rounded-md bg-background-50 p-3 text-xs"><p className="break-all text-foreground-500">{record.source ? `${record.source}${record.target ? ` → ${record.target}` : ""}` : `成员：${record.members.join("、")}`}</p><pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap break-all leading-6">{JSON.stringify(record.data, null, 2)}</pre></div>)}
        {related.items.length === 0 && <p className="text-sm text-foreground-500">没有相关记录。</p>}
      </Card>)}
    </>}
  </div>;
}
