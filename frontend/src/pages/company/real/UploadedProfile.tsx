import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { requestEnterpriseCompany, requestPredictModel } from "@/entities/modeling/api/modelingApi";
import { displayEnterpriseValue, enterpriseName } from "@/entities/modeling/lib/enterpriseDisplay";
import type { ResponseEnterpriseCompany } from "@/shared/api/generated/schema";
import { handleApiError } from "@/shared/api/http";
import Card from "@/shared/ui/Card";
import { EnterpriseProperties } from "./EnterpriseProperties";
import { EnterpriseSourceTrace } from "./EnterpriseSourceTrace";

export default function UploadedProfile() {
  const { datasetId = "", companyId = "" } = useParams();
  const [params] = useSearchParams();
  const modelId = params.get("model") ?? "";
  const [data, setData] = useState<ResponseEnterpriseCompany>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    setData(undefined); setError("");
    requestEnterpriseCompany({ datasetId, companyId, modelId: modelId || undefined }).then((result) => { if (active) setData(result); }).catch((cause) => {
      if (active) setError(handleApiError(cause, { MODELING_COMPANY_NOT_FOUND: "当前数据集中没有此企业。" }));
    });
    return () => { active = false; };
  }, [datasetId, companyId, modelId, revision]);
  async function predict() {
    setBusy(true); setError("");
    try { await requestPredictModel({ modelId, companyIds: [companyId] }); setRevision((value) => value + 1); }
    catch (cause) { setError(handleApiError(cause, { RISKGNN_COMPANY_NOT_FOUND: "该企业不在此模型保存的训练图中，无法用当前模型预测。" })); }
    finally { setBusy(false); }
  }
  const back = `/search?source=uploaded&dataset=${encodeURIComponent(datasetId)}${modelId ? `&model=${encodeURIComponent(modelId)}` : ""}`;
  return <div className="space-y-5">
    <div className="flex items-center justify-between"><h1 className="text-2xl font-semibold">企业详情</h1><Link to={back} className="text-xs text-primary-400">← 返回本数据集检索</Link></div>
    {error && <p role="alert" className="rounded-lg border border-danger-500/30 p-4 text-sm text-danger-500">{error}</p>}
    {!data && !error && <p role="status" className="text-sm text-foreground-500">正在加载企业详情…</p>}
    {data && <>
      <section className="rounded-lg border border-background-200 bg-background-100 p-5"><h2 className="text-xl font-semibold">{enterpriseName(data.company)}</h2><p className="mt-2 break-all font-mono text-xs text-foreground-500">{companyId}</p><p className="mt-3 text-sm text-foreground-500">数据集：{data.dataset.name} · 快照：{data.company.snapshot} · 已有标签：{displayEnterpriseValue(data.company.data.label)}</p><Link className="mt-3 inline-block text-xs text-primary-400" to={`/?source=uploaded&dataset=${encodeURIComponent(datasetId)}`}>查看本数据集总览 →</Link></section>
      <EnterpriseProperties data={data.company.data} />
      <EnterpriseSourceTrace provenance={data.provenance} />
      <Card title="模型预测" subtitle="以下为各模型已有预测，主分类概率未校准。" icon="ri-cpu-line" bodyClassName="space-y-3 p-5">
        {data.predictions.map((prediction) => <div key={prediction.modelId} className="rounded-md border border-background-200 p-4"><p className="text-sm font-medium">{prediction.modelName}</p><p className="mt-1 font-mono text-[10px] text-foreground-500">{prediction.modelId}</p><p className="mt-3 text-sm">主分类概率 {(prediction.result.probability * 100).toFixed(2)}% · 类别 {prediction.result.predictedLabel}</p><p className="mt-2 text-xs text-foreground-500">融合概率：{prediction.result.fusedProbability == null ? "—" : `${(prediction.result.fusedProbability * 100).toFixed(2)}%`} · 不确定性：{prediction.result.uncertainty == null ? "—" : `${(prediction.result.uncertainty * 100).toFixed(2)}%`} · 冲突：{prediction.result.conflict == null ? "—" : `${(prediction.result.conflict * 100).toFixed(2)}%`}</p></div>)}
        {data.predictions.length === 0 && <p className="text-sm text-foreground-500">该企业尚无已保存的预测结果。</p>}
        {modelId && <button type="button" disabled={busy} onClick={() => void predict()} className="rounded-md bg-primary-500 px-4 py-2 text-xs text-white disabled:opacity-50">{busy ? "正在预测…" : "使用检索时选择的模型预测"}</button>}
        <Link to={`/modeling?dataset=${encodeURIComponent(datasetId)}&tab=model`} className="ml-3 text-xs text-primary-400">打开工作台模型管理</Link>
      </Card>
      {Object.entries(data.related).map(([kind, related]) => <Card key={kind} title={`${({ edge: "普通关系", hyperedge: "超边", event: "事件" } as Record<string, string>)[kind] ?? kind} · ${related.total.toLocaleString()} 条`} subtitle={`仅展示同快照中与该企业相关的前${related.items.length}条记录。`} icon="ri-share-line" bodyClassName="space-y-3 p-4">
        {related.items.map((record) => <div key={record.sequence} className="rounded-md bg-background-50 p-3 text-xs"><p className="break-all text-foreground-500">{record.source ? `${record.source}${record.target ? ` → ${record.target}` : ""}` : `成员：${record.members.join("、")}`}</p><pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap break-all leading-6">{JSON.stringify(record.data, null, 2)}</pre></div>)}
        {related.items.length === 0 && <p className="text-sm text-foreground-500">没有相关记录。</p>}
      </Card>)}
    </>}
  </div>;
}
