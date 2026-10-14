import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { requestAskData, requestDataQACatalog } from "@/features/data-qa/api/dataQaApi";
import type { ResponseAskData, ResponseDataQACatalog } from "@/shared/api/generated/schema";
import { handleApiError } from "@/shared/api/http";

const examples = [
  "我有哪些数据集？列出名称和校验状态",
  "各数据集分别导入了多少家企业？",
  "训练实验按执行状态分别有多少个？",
  "列出风险概率最高的前10条预测，包含模型名称和企业ID",
  "各模型已保存预测中，高风险和低风险分别有多少条？",
  "普通关系、超边和事件分别有多少条？",
];
const errors = {
  CHAT_NOT_CONFIGURED: "后端尚未配置内网大模型密钥。",
  CHAT_UNREACHABLE: "无法连接内网大模型，请检查后端网络。",
  CHAT_TIMEOUT: "大模型响应超时，请稍后重试。",
  CHAT_AUTH_FAILED: "内网大模型认证失败，请检查后端密钥。",
  CHAT_UPSTREAM_ERROR: "内网大模型服务返回错误。",
  CHAT_INVALID_RESPONSE: "内网大模型返回格式异常。",
  DATA_QA_SCOPE_NOT_FOUND: "所选数据集或模型已不可用，请刷新查询范围。",
  DATA_QA_PLAN_INVALID: "模型未生成有效查询，请简化问题后重试。",
  DATA_QA_UNSUPPORTED: "当前问题超出可查询范围。请根据下方表结构询问数量、分组统计或明细，JSON属性内部统计暂未开放。",
  DATA_QA_TIMEOUT: "问数规划超时，请简化问题或稍后重试。",
  DATA_QA_DATABASE_UNAVAILABLE: "工作台数据库暂时不可用，请检查后端服务。",
  DATA_QA_QUERY_FAILED: "数据库查询未完成，请缩小查询范围后重试。",
};
const panel = "rounded-xl border border-background-200 bg-background-100 p-5";
const input = "mt-2 w-full rounded-md border border-background-300 bg-background-50 p-2.5 text-sm outline-none focus:border-primary-500 disabled:opacity-50";
const button = "rounded-md bg-primary-500 px-5 py-2.5 text-sm text-white disabled:opacity-50";
function cell(value: unknown): string {
  if (value === null || value === undefined) return "—";
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

type SavedResult = { data: ResponseAskData; scope: string };

export default function DataQAPage() {
  const [catalog, setCatalog] = useState<ResponseDataQACatalog>();
  const [catalogError, setCatalogError] = useState("");
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const [dataset, setDataset] = useState("");
  const [model, setModel] = useState("");
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [history, setHistory] = useState<SavedResult[]>([]);
  const [selected, setSelected] = useState(0);
  const locked = useRef(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setCatalogError("");
    requestDataQACatalog({}).then((data) => {
      if (active) { setCatalog(data); setDataset(""); setModel(""); }
    }).catch((cause) => {
      if (active) setCatalogError(handleApiError(cause, errors));
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [revision]);

  async function submit() {
    if (locked.current || !question.trim() || !catalog) return;
    locked.current = true;
    setBusy(true);
    setError("");
    const scope = `${catalog.datasets.find((item) => item.id === dataset)?.name ?? "全部数据集"} · ${catalog.models.find((item) => item.id === model)?.name ?? "全部模型"}`;
    try {
      const data = await requestAskData({ question: question.trim(), datasetId: dataset || undefined, modelId: model || undefined });
      setHistory((items) => [{ data, scope }, ...items].slice(0, 10));
      setSelected(0);
    } catch (cause) {
      setError(handleApiError(cause, errors));
    } finally {
      locked.current = false;
      setBusy(false);
    }
  }

  const current = history[selected];
  const result = current?.data;
  const groups = Array.isArray(result?.plan.groupBy) ? result.plan.groupBy.filter((value): value is string => typeof value === "string") : [];
  const dimension = result?.columns.find((column) => column.id === groups[0])
    ?? result?.columns.find((column) => column.id === "company_id")
    ?? result?.columns.find((column) => column.type === "text" || column.type === "datetime");
  const metrics = result?.columns.filter((column) => column.type === "number" && column.id !== "sequence").slice(0, 1) ?? [];
  const chartRows = result?.rows.slice(0, 20).map((row) => ({ ...row, category: groups.length > 0 ? groups.map((id) => cell(row[id])).join(" · ") : dimension ? cell(row[dimension.id]) : "" })) ?? [];
  const availableModels = catalog?.models.filter((item) => !dataset || item.datasetId === dataset) ?? [];

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground-950">工作台问数</h1>
          <p className="mt-2 text-sm text-foreground-500">用自然语言查询工作台数据库，查看真实统计、明细和查询依据。</p>
        </div>
        <span className="rounded-full border border-primary-500/30 bg-primary-500/10 px-3 py-1 text-xs text-primary-400">表结构 + 业务口径 · 只读查询</span>
      </div>
      <form onSubmit={(event) => { event.preventDefault(); void submit(); }} className={`${panel} space-y-4`}>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="text-sm font-medium">数据集范围
            <select value={dataset} disabled={loading || busy || !catalog} onChange={(event) => { setDataset(event.target.value); setModel(""); }} className={input}>
              <option value="">当前账号的全部数据集</option>
              {catalog?.datasets.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.id.slice(0, 8)}</option>)}
            </select>
          </label>
          <label className="text-sm font-medium">预测模型范围（仅影响预测查询）
            <select value={model} disabled={loading || busy || !catalog} onChange={(event) => setModel(event.target.value)} className={input}>
              <option value="">范围内的全部模型</option>
              {availableModels.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.id.slice(0, 8)}</option>)}
            </select>
          </label>
        </div>
        <p className="text-xs text-foreground-500">每次问题独立查询；最多返回100行。企业数据需先导入，预测统计只包含已保存结果。</p>
        {loading && <p role="status" className="text-sm text-foreground-500">正在读取可查询的数据范围…</p>}
        {catalogError && <p role="alert" className="text-sm text-red-500">{catalogError}</p>}
        {!loading && <button type="button" disabled={busy} onClick={() => setRevision((value) => value + 1)} className="text-xs text-primary-400 disabled:opacity-50">刷新查询范围</button>}
        {catalog && catalog.datasets.length === 0 && <p className="text-sm text-foreground-500">当前账号尚未登记训练数据集。企业演示数据、页面案例及报告请前往 <Link className="text-primary-400 underline" to="/chat">智能助手的统一数据资产目录</Link> 查看。</p>}
        {catalog?.truncated && <p className="text-xs text-amber-500">范围选择器显示最近200个数据集/模型；全部范围查询仍包含当前账号的全部记录。</p>}
        <label htmlFor="data-question" className="block text-sm font-medium">你的问题
          <textarea id="data-question" value={question} disabled={busy} onChange={(event) => setQuestion(event.target.value)} maxLength={2000} rows={3} className={input} placeholder="例如：各数据集分别导入了多少家企业？" />
        </label>
        <div className="flex flex-wrap gap-2">
          {examples.map((text) => <button key={text} type="button" disabled={busy} onClick={() => setQuestion(text)} className="rounded-md border border-background-300 px-2.5 py-1.5 text-xs text-foreground-500 hover:border-primary-500 hover:text-primary-400 disabled:opacity-50">{text}</button>)}
        </div>
        <div className="flex items-center justify-between gap-3">
          <span role="status" className="text-xs text-foreground-500">{busy ? "正在理解问题、校验查询计划并读取数据库…" : `${question.length} / 2000`}</span>
          <button type="submit" disabled={busy || loading || !!catalogError || !catalog || !question.trim()} className={button}>{busy ? "正在查询…" : "开始问数"}</button>
        </div>
      </form>
      {error && <p role="alert" className="rounded-lg border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-500">{error}</p>}
      {history.length > 1 && <label className="block text-sm text-foreground-500">本页最近查询（刷新后清空）
        <select className={input} value={selected} onChange={(event) => setSelected(Number(event.target.value))}>
          {history.map((item, index) => <option key={index} value={index}>{index + 1}. {item.data.question}</option>)}
        </select>
      </label>}
      {result && <section aria-label="问数结果" className={`${panel} space-y-5`}>
        <div>
          <p className="text-xs text-foreground-500">{current.scope} · {result.model} · {(result.elapsedMs / 1000).toFixed(2)} 秒</p>
          <h2 className="mt-2 text-lg font-medium">{result.question}</h2>
          <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-primary-400">{result.answer}</p>
        </div>
        {result.warnings.length > 0 && <ul className="space-y-1 rounded-lg bg-amber-500/10 p-3 text-xs leading-6 text-amber-500">{result.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>}
        {dimension && metrics.length > 0 && result.rows.length > 1 && <div>
          <p className="mb-3 text-xs text-foreground-500">结果图表 · 前{chartRows.length}行 · {dimension.name}</p>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartRows} margin={{ top: 10, right: 15, bottom: 20, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                <XAxis dataKey="category" tick={{ fontSize: 10 }} tickFormatter={(value: string) => value.length > 16 ? `${value.slice(0, 16)}…` : value} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip />
                {metrics.map((column, index) => <Bar key={column.id} dataKey={column.id} name={column.name} fill={["#3b82f6", "#d4a253", "#4fa89b"][index]} radius={[3, 3, 0, 0]} />)}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead><tr>{result.columns.map((column) => <th key={column.id} className="whitespace-nowrap border-b border-background-300 px-3 py-3 font-medium">{column.name}</th>)}</tr></thead>
            <tbody>{result.rows.map((row, index) => <tr key={index}>{result.columns.map((column) => <td key={column.id} className="max-w-md break-words border-b border-background-200 px-3 py-3 align-top">{cell(row[column.id])}</td>)}</tr>)}</tbody>
          </table>
          {result.rows.length === 0 && <p className="py-8 text-center text-sm text-foreground-500">没有匹配记录，查询条件已保留。</p>}
        </div>
        <details className="rounded-lg border border-background-200 p-3">
          <summary className="cursor-pointer text-sm text-primary-400">查看 SQL、查询计划和过程</summary>
          <p className="my-3 text-xs text-foreground-500">版本：{result.promptVersion} · 语义视图：{result.table} · SQL中的参数由后端绑定</p>
          <ol className="mb-3 list-inside list-decimal space-y-1 text-xs text-foreground-500">{result.steps.map((step) => <li key={step}>{step}</li>)}</ol>
          <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-md bg-background-50 p-3 text-xs leading-6">{result.sql}</pre>
          <pre className="mt-3 max-h-80 overflow-auto rounded-md bg-background-50 p-3 text-xs">{JSON.stringify(result.plan, null, 2)}</pre>
        </details>
      </section>}
      {catalog && <details className={panel}>
        <summary className="cursor-pointer text-sm font-medium">可查询的表结构与字段（{catalog.tables.length}个视图）</summary>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {catalog.tables.map((table) => <div key={table.id} className="rounded-lg border border-background-200 p-3">
            <h3 className="text-sm font-medium">{table.name}</h3>
            <p className="my-2 break-all font-mono text-[11px] text-foreground-500">{table.physicalTable} → {table.id}</p>
            <p className="text-xs leading-6 text-foreground-500">{table.fields.map((field) => `${field.name} (${field.id})`).join(" · ")}</p>
          </div>)}
        </div>
      </details>}
    </div>
  );
}
