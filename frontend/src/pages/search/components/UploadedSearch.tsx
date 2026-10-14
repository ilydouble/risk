import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { requestEnterpriseOverview, requestListEnterpriseRecords } from "@/entities/modeling/api/modelingApi";
import { displayEnterpriseValue, enterpriseLink, enterpriseName } from "@/entities/modeling/lib/enterpriseDisplay";
import EnterpriseSyncNotice from "@/features/enterprise-browser/ui/EnterpriseSyncNotice";
import type { components, ResponseEnterpriseOverview, ResponseListEnterpriseRecords } from "@/shared/api/generated/schema";
import { handleApiError } from "@/shared/api/http";

type EnterpriseSourceDTO = components["schemas"]["EnterpriseSourceDTO"];

export default function UploadedSearch({ datasetId, source, onImported }: { datasetId: string; source?: EnterpriseSourceDTO; onImported: () => void }) {
  const [params, setParams] = useSearchParams();
  const query = params.get("q") ?? "";
  const model = params.get("model") ?? "";
  const [input, setInput] = useState(query);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ResponseListEnterpriseRecords>();
  const [summary, setSummary] = useState<ResponseEnterpriseOverview>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  useEffect(() => { setInput(query); setPage(1); }, [query, model]);
  useEffect(() => {
    let active = true;
    requestEnterpriseOverview({ datasetId }).then((value) => { if (active) setSummary(value); }).catch((cause) => { if (active) setError(handleApiError(cause)); });
    return () => { active = false; };
  }, [datasetId, revision, source?.importStatus]);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      setLoading(true);
      try {
        const result = await requestListEnterpriseRecords({ datasetId, kind: "company", keyword: query, modelId: model || undefined, pagination: { page, pageSize: 20 } });
        if (!active) return;
        setData(result); setError("");
        if (!result.imported) timer = setTimeout(() => void load(), 5000);
      } catch (cause) { if (active) setError(handleApiError(cause)); }
      finally { if (active) setLoading(false); }
    }
    void load();
    return () => { active = false; clearTimeout(timer); };
  }, [datasetId, query, model, page, revision]);
  function change(key: string, value: string) {
    setPage(1);
    setParams((previous) => { const next = new URLSearchParams(previous); next.set("source", "uploaded"); next.set("dataset", datasetId); if (value) next.set(key, value); else next.delete(key); return next; });
  }
  const reload = () => { setRevision((value) => value + 1); onImported(); };
  const currentSource = source ?? summary?.dataset;
  return <div className="space-y-4">
    <header><h1 className="text-2xl font-semibold">企业检索 · {currentSource?.name ?? datasetId}</h1><p className="mt-2 text-xs text-foreground-500">查询当前数据集已导入的全量企业，按企业名称或 ID 检索。</p></header>
    {currentSource && <EnterpriseSyncNotice dataset={currentSource} refresh={reload} />}
    <form onSubmit={(event) => { event.preventDefault(); change("q", input.trim()); }} className="flex flex-wrap gap-3 rounded-lg border border-background-200 bg-background-100 p-4">
      <input aria-label="企业名称或ID" value={input} onChange={(event) => setInput(event.target.value)} placeholder="输入企业名称或 ID" className="min-w-48 flex-1 rounded-md border border-background-300 bg-background-50 px-3 py-2 text-sm" />
      <select aria-label="显示模型预测" value={model} onChange={(event) => change("model", event.target.value)} className="max-w-xs rounded-md border border-background-300 bg-background-50 px-3 py-2 text-sm">
        <option value="">仅浏览企业，不叠加模型预测</option>
        {summary?.models.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.id.slice(0, 8)}</option>)}
      </select>
      <button type="submit" className="rounded-md bg-primary-500 px-4 py-2 text-sm text-white">检索</button>
      <button type="button" onClick={reload} className="text-xs text-primary-400">刷新</button>
      <Link className="self-center text-xs text-primary-400" to={`/?source=uploaded&dataset=${encodeURIComponent(datasetId)}`}>查看总览</Link>
    </form>
    {model && <p className="text-xs text-foreground-500">仅叠加该模型已保存的预测；空白表示尚未评估，不代表低风险。</p>}
    {loading && <p role="status" className="text-sm text-foreground-500">正在检索…</p>}
    {error && <p role="alert" className="text-sm text-danger-500">{error}</p>}
    {!loading && !error && data && <>
      <p className="text-xs text-foreground-500">匹配企业 {data.total.toLocaleString()} 家 · 第 {page} / {Math.max(1, Math.ceil(data.total / 20))} 页</p>
      <div className="overflow-x-auto rounded-lg border border-background-200 bg-background-100">
        <table className="w-full min-w-[680px] text-left text-xs"><thead><tr>{["企业 / ID", "快照", "已有标签", "模型预测", "操作"].map((name) => <th key={name} className="border-b border-background-200 p-4">{name}</th>)}</tr></thead>
          <tbody>{data.items.map((company) => <tr key={company.sequence} className="border-b border-background-200 last:border-0"><td className="p-4"><p className="text-sm font-medium">{enterpriseName(company)}</p><p className="mt-1 break-all font-mono text-[10px] text-foreground-500">{company.nodeId}</p></td><td className="p-4">{company.snapshot}</td><td className="p-4">{displayEnterpriseValue(company.data.label)}</td><td className="p-4">{company.prediction ? <><p>正类概率 {(company.prediction.probability * 100).toFixed(2)}% · 类别 {company.prediction.predictedLabel}</p>{company.prediction.uncertainty != null && <p className="mt-1 text-foreground-500">不确定性 {(company.prediction.uncertainty * 100).toFixed(2)}%</p>}</> : model ? "尚未评估" : "未选择模型"}</td><td className="p-4"><Link className="text-primary-400" to={`${enterpriseLink(datasetId, company.nodeId!)}${model ? `&model=${encodeURIComponent(model)}` : ""}`}>企业详情 →</Link></td></tr>)}</tbody>
        </table>
        {data.items.length === 0 && <p className="p-10 text-center text-sm text-foreground-500">{data.imported ? "没有匹配的企业。" : "企业数据尚在校验或导入中。"}</p>}
      </div>
      <div className="flex justify-end gap-4 text-xs"><button type="button" disabled={page <= 1} className="disabled:opacity-40" onClick={() => setPage((value) => value - 1)}>上一页</button><button type="button" disabled={page * 20 >= data.total} className="disabled:opacity-40" onClick={() => setPage((value) => value + 1)}>下一页</button></div>
    </>}
  </div>;
}
