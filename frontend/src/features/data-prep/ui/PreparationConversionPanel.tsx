import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { ResponseConversionState } from "@/shared/api/generated/schema";
import { handleApiError } from "@/shared/api/http";
import { requestGetConversion, requestImportConversion, requestTrialConversion } from "../api/dataPrepApi";

export function PreparationConversionPanel({ preparationId, disabled = false, revision = "", onAsk }: {
  preparationId: string;
  disabled?: boolean;
  revision?: string;
  onAsk?: () => void;
}) {
  const [result, setResult] = useState<ResponseConversionState>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmedTask, setConfirmedTask] = useState("");
  useEffect(() => {
    if (disabled) return;
    let active = true;
    requestGetConversion({ preparationId }).then(value => {
      if (active) { setResult(value); setError(""); }
    }).catch(cause => { if (active) setError(handleApiError(cause)); });
    return () => { active = false; };
  }, [preparationId, disabled, revision]);
  const data = result?.preparationId === preparationId ? result : undefined;
  const task = data?.task;
  const blocked = disabled || busy;
  async function execute(importing: boolean) {
    if (blocked || !data || !data.planCurrent) return;
    if (importing && (!task || !task.current || confirmedTask !== task.id)) return;
    setBusy(true); setError(""); setConfirmedTask("");
    try {
      const next = importing && task
        ? await requestImportConversion({ preparationId, taskId: task.id, confirm: true })
        : await requestTrialConversion({ preparationId });
      setResult(next);
    } catch (cause) { setError(handleApiError(cause)); }
    finally { setBusy(false); }
  }
  const button = "rounded-lg border border-background-300 px-3 py-2 text-xs disabled:opacity-40";
  return <section aria-label="转换核验与导入" className="mt-3 space-y-3 rounded-xl border border-background-200 bg-background-100 p-4 text-xs">
    <div className="flex flex-wrap items-center justify-between gap-3"><h3 className="font-semibold">转换核验与导入</h3>
      {onAsk && <button disabled={blocked} onClick={onAsk} className={button}>让助手保存规则并试运行</button>}
    </div>
    {!data && !error && <p role="status">正在读取转换方案…</p>}
    {data && !data.plan && <p className="leading-6 text-foreground-500">尚无可执行规则。请与助手确认字段用途、缺失值和去重方式，再让助手保存规则并试运行。自然语言映射本身不会执行。</p>}
    {data?.plan && <>
      <p className="leading-6 text-foreground-500">导入企业属性及案例中已核验的图关系，供概览与检索使用；不会推测关系、生成训练划分或模型预测。完全重复行：{data.plan.deduplicate === "exact" ? "保留一条" : "不自动删除，重复标识将阻止导入"}。</p>
      {!data.planCurrent && <p role="alert" className="text-amber-600">映射已变更，请让助手重新核对并保存执行规则。</p>}
      <details><summary className="cursor-pointer">查看可执行规则（{data.plan.columns.length} 个字段）</summary>
        <div className="mt-2 overflow-x-auto"><table className="min-w-full text-left"><thead><tr>{["源字段", "目标", "类型", "缺失值", "填充值 / 标签映射"].map(name => <th key={name} className="p-2">{name}</th>)}</tr></thead><tbody>{data.plan.columns.map(column => <tr key={column.field} className="border-t border-background-200"><td className="p-2">{column.field}</td><td className="p-2">{column.target || "忽略"}</td><td className="p-2">{column.type}</td><td className="p-2">{column.missing}<p className="max-w-48 break-words text-foreground-500">识别值：{JSON.stringify(column.missingValues)}</p></td><td className="p-2">{column.type === "label" ? JSON.stringify(column.values) : column.missing === "fill" ? String(column.fill) : "—"}</td></tr>)}</tbody></table></div>
        {data.plan.labelMeaning && <p className="mt-2 leading-6">标签定义：{data.plan.labelMeaning}</p>}
      </details>
      <button disabled={blocked || !data.planCurrent} onClick={() => void execute(false)} className={button}>{busy ? "正在处理…" : "试运行并核验"}</button>
    </>}
    {task && <div className="space-y-3 border-t border-background-200 pt-3">
      <p role="status" className="font-medium">{task.status === "imported" ? "已正式导入" : !task.current ? "试运行结果已过期" : task.status === "ready" ? "试运行通过，待确认导入" : "试运行未通过，请处理问题后重试"}</p>
      <div className="flex flex-wrap gap-4"><span>输入 CSV {task.report.inputCount} 行</span><span>输出 {task.report.counts?.company ?? task.report.outputCount} 家企业</span>{task.report.graph && <><span>关系 {task.report.counts?.edge ?? 0} 条</span><span>群组 {task.report.counts?.hyperedge ?? 0} 组</span></>}<span>去重 {task.report.duplicateCount} 行</span><span>拒绝 {task.report.rejectedCount} 行/项</span></div>
      {task.report.graph && <div className="space-y-2 rounded-lg bg-background-50 p-3"><p className="font-medium">企业 ID 关联核验</p><p>图引用 {task.report.graph.referencedCount} 家 · 匹配 {task.report.graph.matchedCount} 家 · 缺失 {task.report.graph.missingCount} 家 · 属性/关系冲突 {task.report.graph.conflictCount} 项 · 完全重复关系 {task.report.graph.duplicateCount} 条</p>{task.report.graph.files.map(file => <p key={file.filename}>{file.filename}：引用 {file.referencedCount}，匹配 {file.matchedCount}，缺失 {file.missingCount}</p>)}{task.report.graph.missingIds.length > 0 && <p className="break-all">缺失企业示例：{task.report.graph.missingIds.join("、")}</p>}</div>}
      {task.report.warnings.map((warning, index) => <p key={index} className="text-foreground-500">{warning}</p>)}
      {task.report.issues.length > 0 && <div><p>共 {task.report.issueCount} 条错误，展示前 {task.report.issues.length} 条。存在拒绝记录时不允许部分导入。</p><ul className="mt-2 list-disc space-y-1 pl-5">{task.report.issues.map((issue, index) => <li key={index}>{issue.filename ? `${issue.filename} · ${issue.path}` : `CSV 第 ${issue.line} 行`}：{issue.message}</li>)}</ul></div>}
      <details><summary className="cursor-pointer">查看转换前后样例（前 {task.report.examples.length} 条成功记录，长文本最多显示200字符）</summary><div className="mt-2 space-y-3">{task.report.examples.map(example => <div key={example.line}><p>CSV 第 {example.line} 行</p><div className="grid gap-2 sm:grid-cols-2"><pre className="max-h-52 overflow-auto whitespace-pre-wrap break-all rounded bg-background-50 p-2">{JSON.stringify(example.before, null, 2)}</pre><pre className="max-h-52 overflow-auto whitespace-pre-wrap break-all rounded bg-background-50 p-2">{JSON.stringify(example.after, null, 2)}</pre></div></div>)}</div></details>
      <details><summary className="cursor-pointer">查看执行依据</summary><p className="mt-2 break-all leading-6">任务：{task.id}<br />执行器：{task.engineVersion}<br />规则版本：{task.planVersion}<br />案例来源 SHA-256：{task.sourceSha256}<br />产物 SHA-256：{task.outputSha256}</p></details>
      {task.status === "ready" && task.current && data?.planCurrent && <>
        <label className="flex items-start gap-2 leading-6"><input type="checkbox" disabled={blocked} checked={confirmedTask === task.id} onChange={event => setConfirmedTask(event.target.checked ? task.id : "")} />我已核对上述转换规则、前后样例和数量变化，确认将结果导入当前账号。</label>
        <button disabled={blocked || confirmedTask !== task.id} onClick={() => void execute(true)} className={`${button} bg-primary-500 text-white`}>{busy ? "正在导入…" : "确认并导入"}</button>
      </>}
      {task.datasetId && <div className="flex gap-4 text-primary-500"><Link to={`/?source=uploaded&dataset=${encodeURIComponent(task.datasetId)}`}>查看概览 →</Link><Link to={`/search?source=uploaded&dataset=${encodeURIComponent(task.datasetId)}`}>进入检索 →</Link></div>}
    </div>}
    {error && <p role="alert" className="text-red-500">{error}</p>}
  </section>;
}
