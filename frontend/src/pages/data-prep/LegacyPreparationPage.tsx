import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { requestInspectCase, requestSuggestMapping, requestListPreparations, requestGetPreparation } from "@/features/data-prep/api/dataPrepApi";
import { useAiModelConfig } from "@/features/ai-model-config/model/context";
import { useDataPrepSession } from "@/features/data-prep/model/context";
import { handleApiError } from "@/shared/api/http";
import { DatasetDeliveryPanel } from "@/features/dataset-delivery/ui/DatasetDeliveryPanel";
import { ReportGenerationStatus } from "./ReportGenerationStatus";

import { PreparationDeleteButton } from "@/features/data-prep/ui/PreparationDeleteButton";
import { PreparationMappingEditor } from "@/features/data-prep/ui/PreparationMappingEditor";
import { PreparationConversionPanel } from "@/features/data-prep/ui/PreparationConversionPanel";
import type { ResponsePreparation } from "@/shared/api/generated/schema";

const panel = "rounded-xl border border-background-200 bg-background-100 p-5";
const button = "rounded-md bg-primary-500 px-4 py-2 text-sm text-white disabled:opacity-50";
const typeLabels: Record<string, string> = {
  empty: "全缺失", identifier: "标识符线索", number: "数值", date: "日期", mixed: "混合格式", category: "类别", text: "文本",
};
const roleLabels: Record<string, string> = {
  identity: "实体标识", feature: "候选特征", label: "候选标签", relation: "关系键", time: "时间", ignore: "暂不使用", unknown: "待确认",
};

function fileBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1] ?? "");
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

export default function DataPrepPage() {
  const modelConfig = useAiModelConfig();
  const { files, profile, suggestion, preparation, setPreparation, setFiles, setProfile, setSuggestion } = useDataPrepSession();
  const [params, setParams] = useSearchParams();
  const preparationId = params.get("preparation");
  const [saved, setSaved] = useState<ResponsePreparation[]>([]);
  const [savedTruncated, setSavedTruncated] = useState(false);
  const [busy, setBusy] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const pendingFiles = files.length > 0;
  const legacyProfile = profile?.fields.some((field) => !Array.isArray(field.topValues));

  useEffect(() => {
    let active = true;
    requestListPreparations({ workbenchOnly: false }).then(result => {
      if (active) { setSaved(result.items); setSavedTruncated(result.truncated); }
    }).catch(cause => { if (active) setError(handleApiError(cause)); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    if (!preparationId) return;
    setFiles([]); setPreparation(undefined); setProfile(undefined); setSuggestion(undefined);
    let active = true;
    requestGetPreparation({ preparationId }).then(item => {
      if (active) { setPreparation(item); setProfile(item.profile); setSuggestion(item.report ?? undefined); }
    }).catch(cause => { if (active) setError(handleApiError(cause)); });
    return () => { active = false; };
  }, [preparationId, setFiles, setPreparation, setProfile, setSuggestion]);

  async function inspect() {
    if (!files.length || busy) return;
    setBusy(true); setError("");
    try {
      const item = await requestInspectCase({
        preparationId: preparation?.id,
        files: await Promise.all(files.map(async file => ({ filename: file.name, contentBase64: await fileBase64(file) }))),
      });
      setProfile(item.profile); setPreparation(item); setSuggestion(item.report ?? undefined);
      setFiles([]);
      setSaved(current => [item, ...current.filter(value => value.id !== item.id)]);
      setParams({ preparation: item.id });
    } catch (cause) { setError(handleApiError(cause)); }
    finally { setBusy(false); }
  }

  function newCase() {
    setFiles([]); setProfile(undefined); setSuggestion(undefined); setPreparation(undefined); setParams({}); setError("");
  }

  async function suggest() {
    if (!profile || busy || pendingFiles) return;
    setBusy(true);
    setGenerating(true);
    setError("");
    try {
      setSuggestion(await requestSuggestMapping({ profile, connection: modelConfig.connection, maxTokens: modelConfig.maxTokens }));
      if (profile.preparationId) setPreparation(await requestGetPreparation({ preparationId: profile.preparationId }));
    } catch (cause) {
      setError(handleApiError(cause, {
        CHAT_NOT_CONFIGURED: "智能分析需要先配置后端大模型。数据体检结果仍可查看。",
        CHAT_UNREACHABLE: "暂时无法连接大模型，请稍后重试。",
        CHAT_TIMEOUT: "模型服务连接或响应超时，请检查后端到模型服务的网络。",
        CHAT_AUTH_FAILED: "模型认证失败，请在智能体模型设置中检查 API 密钥。",
        CHAT_OUTPUT_LIMIT: "模型输出达到本次上限，请在智能体模型设置中提高“单次回答上限”后重试。",
        CHAT_UPSTREAM_ERROR: "模型服务未能完成工具调用，请确认所选接口支持 Chat Completions 工具调用。",
        DATA_PREP_SUGGESTION_INVALID: "智能体未完成工具分析或报告格式无效，请重试。",
      }));
    } finally {
      setGenerating(false);
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <header>
        <h1 className="text-2xl font-semibold text-foreground-950">数据准备</h1>
        <p className="mt-2 text-sm text-foreground-500">借助智能体分析原始材料、确认转换规则，再生成并交付工作台需要的数据包。</p>
      </header>
      <nav aria-label="数据准备流程" className="flex gap-3">
        {[ ["analysis", "1. 智能体分析与转换"], ["delivery", "2. 训练包生成与交付"] ].map(([key, label]) => <button key={key} className={params.get("step") === key || (!params.get("step") && key === "analysis") ? button : "rounded-md border border-background-300 px-4 py-2 text-sm"} onClick={() => setParams(previous => { const next = new URLSearchParams(previous); next.set("step", key); return next; })}>{label}</button>)}
      </nav>
      {params.get("step") === "delivery" ? <DatasetDeliveryPanel key={preparationId ?? "standalone"} sourcePreparationId={preparation?.id === preparationId && preparation.confirmed ? preparation.id : undefined} /> : <>
      <div className={`${panel} flex flex-wrap items-center justify-between gap-3 text-sm`}>
        <span>报告使用模型：{modelConfig.custom ? `${modelConfig.model || "自定义模型（未填写）"} · 自定义` : `${modelConfig.defaults?.model || "后端默认模型"} · 后端默认`}</span>
        <Link className="text-primary-400 underline" to="/settings/ai-model">配置智能体模型</Link>
      </div>
      <section className={`${panel} space-y-3`}>
        {saved.length > 0 && <label className="block text-sm">继续已保存的案例<select aria-label="已保存的数据准备" className="ml-3 rounded-md border border-background-300 bg-background-50 p-2" disabled={busy} value={preparation?.id ?? ""} onChange={event => { if (event.target.value) { setFiles([]); setParams({ preparation: event.target.value }); } }}><option value="">选择案例</option>{saved.map(item => <option key={item.id} value={item.id}>{item.filename} · {item.profile.rowCount} 行{item.confirmed ? " · 映射已确认" : ""}</option>)}</select>{savedTruncated && <span className="ml-2 text-xs text-foreground-500">显示最近100份</span>}</label>}
        <div className="flex items-center justify-between gap-3"><h2 className="font-semibold">{preparation ? "向当前案例补充文件" : "建立多文件数据准备案例"}</h2>{preparation && <button className="text-sm text-primary-500 underline" disabled={busy} onClick={newCase}>新建案例</button>}</div>
        <p className="text-sm text-foreground-500">一个案例包含一张企业属性 CSV 和多个图 JSON，可一次选择或分批添加。CSV 最多 2 MiB、50000 行；每个 JSON 最多 64 MiB，案例最多 8 个文件、共 96 MiB。文件先按案例保存，关系按确认后的企业 ID 规则核验，确认导入后才进入概览与检索。</p>
        {preparation && <PreparationDeleteButton key={preparation.id} preparationId={preparation.id} disabled={busy || pendingFiles} onDeleted={() => { setSaved(current => current.filter(item => item.id !== preparation.id)); newCase(); }} />}
        {preparation && <p className="text-xs text-foreground-500">补充文件将保存为新的案例版本，需重新生成联合报告、确认规则和试运行；原案例、对话及已导入结果保持可追溯。</p>}
        <input aria-label="添加案例文件" type="file" multiple accept=".csv,.json,text/csv,application/json" disabled={busy} onChange={event => { const selected = Array.from(event.target.files ?? []); setFiles(current => [...current, ...selected]); event.target.value = ""; }} />
        {files.length > 0 && <ul className="space-y-2 text-sm">{files.map((file, index) => <li key={`${file.name}-${index}`} className="flex items-center gap-3"><span>{file.name} · {(file.size / 1024).toFixed(1)} KiB · {file.name.toLowerCase().endsWith(".csv") ? "企业属性主表" : "待校验图文件"} · 待保存</span><button disabled={busy} className="text-primary-500 underline" onClick={() => setFiles(current => current.filter((_, i) => i !== index))}>移除</button></li>)}</ul>}
        <div><button className={button} disabled={!files.length || busy} onClick={() => void inspect()}>{busy && !generating ? "保存并分析中…" : "保存并开始体检"}</button></div>
      </section>
      {pendingFiles && preparation && <p role="status" className="text-sm text-amber-600">新增文件尚未保存；请先点击“保存并开始体检”，再分析联合案例或执行导入。</p>}
      {error && <p role="alert" className="text-sm text-red-500">{error}</p>}
      {profile && legacyProfile && <p role="status" className="text-sm text-amber-600">这份案例使用旧版体检统计，请新建案例重新添加原文件进行分析。</p>}
      {profile && !legacyProfile && <>
        <section className={`${panel} space-y-3`} aria-label="案例文件清单">
          <h2 className="font-semibold">案例文件 · 联合分析范围</h2>
          {profile.previousPreparationId && <Link className="text-sm text-primary-500 underline" to={`/data-prep/legacy?preparation=${encodeURIComponent(profile.previousPreparationId)}`}>查看补充文件前的案例版本</Link>}
          <p className="text-sm text-foreground-500">CSV 是企业属性来源；图 JSON 的 nodes 用于关联和属性冲突核验，edges 与 hyperedges 提供关系。尚未核验实际关联覆盖，请保存规则并试运行。</p>
          {profile.caseFiles?.length ? profile.caseFiles.map(file => <div key={file.filename} className="rounded-md bg-background-50 p-3 text-sm"><strong>{file.filename}</strong> · {file.role === "enterprises" ? "企业属性主表" : `图关系 · 节点 ${file.nodeCount} · 边 ${file.edgeCount} · 群组 ${file.hyperedgeCount}`}<p className="mt-1 break-all font-mono text-xs text-foreground-500">SHA-256：{file.sha256}</p>{file.role === "graph" && <p className="mt-1 text-xs">关系：{Object.entries(file.relationTypes).map(([key, count]) => `${key} ${count}`).join(" · ") || "无"}；群组：{Object.entries(file.groupTypes).map(([key, count]) => `${key} ${count}`).join(" · ") || "无"}</p>}</div>) : <p className="text-sm">{preparation?.filename ?? "CSV主表"} · 企业属性主表</p>}
        </section>
        {preparation && <section className={`${panel} flex flex-wrap items-center justify-between gap-4`}>
          <div><h2 className="font-semibold">和助手一起确认映射</h2><p className="mt-2 text-sm text-foreground-500">携带这份案例的体检结果、已有报告和映射草稿，从不确定的问题开始梳理。无需再次上传文件。</p></div>
          {busy || pendingFiles ? <span className="text-sm text-foreground-500">保存并完成当前分析后可进入助手</span> : <Link className={button} to={`/chat?preparation=${encodeURIComponent(preparation.id)}${params.get("conversation") ? `&conversation=${encodeURIComponent(params.get("conversation")!)}` : ""}`}>让助手确认映射</Link>}
        </section>}
        <section className={`${panel} space-y-3`}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div><h2 className="font-semibold">体检结果</h2><p className="text-sm text-foreground-500">统计基于企业属性主表；类型、键和异常只是待核对线索。</p></div>
            <button className={button} disabled={busy || pendingFiles || (modelConfig.custom && (!modelConfig.url.trim() || !modelConfig.model.trim()))} onClick={() => void suggest()}>{busy ? "智能体正在分析…" : "让智能体生成分析报告"}</button>
          </div>
          {generating && <ReportGenerationStatus />}
          <div className="grid gap-3 sm:grid-cols-4">
            {[
              ["记录", profile.rowCount],
              ["字段", profile.fields.length],
              ["含缺失值的记录", profile.rowsWithMissing],
              ["完全重复记录", profile.duplicateRows],
            ].map(([label, value]) => <div key={label} className="rounded-lg bg-background-50 p-3"><p className="text-xs text-foreground-500">{label}</p><p className="mt-1 text-xl font-semibold">{value}</p></div>)}
          </div>
          <p className="text-xs text-foreground-500">案例 SHA-256：<span className="break-all font-mono">{profile.sha256}</span> · 用于核对整个案例文件版本</p>
        </section>
        <section className={`${panel} space-y-3`}>
          <h2 className="font-semibold">数据质量线索 · {profile.issues?.length ?? 0} 项</h2>
          <p className="text-xs text-foreground-500">“未知”、空串、null、n/a 等按缺失统计；疑似离群值按四分位距筛出，不能直接认定为错误。</p>
          {(profile.issues?.length ?? 0) === 0 ? <p className="text-sm text-foreground-500">当前规则未发现明显问题，仍需核对字段语义和取值口径。</p> :
            <div className="grid gap-2 sm:grid-cols-2">{profile.issues?.map((item, index) => <div key={`${item.code}-${item.field ?? "row"}-${index}`} className="rounded-md border border-amber-500/20 bg-amber-500/5 p-3 text-sm"><strong>{item.field || "整表"}</strong> · {item.count} 处<p className="mt-1 text-foreground-500">{item.message}</p></div>)}</div>}
        </section>
        <section className={`${panel} space-y-3`}>
          <h2 className="font-semibold">字段画像</h2>
          <p className="text-xs text-foreground-500">标识列保持文本，尤其是含前导零的企业编号；常见值显示出现次数。数值分布仅适用于数值字段。</p>
          <div className="overflow-x-auto"><table className="min-w-full text-left text-sm"><thead><tr className="border-b border-background-200"><th className="min-w-36 py-2">字段</th><th className="min-w-28">类型线索</th><th className="min-w-28">缺失</th><th className="min-w-24">不同值</th><th className="min-w-64">常见值</th><th className="min-w-72">数值分布</th></tr></thead><tbody>{profile.fields.map((field) => <tr key={field.name} className="border-b border-background-200 align-top"><td className="py-3 font-medium">{field.name}</td><td className="py-3">{typeLabels[field.typeHint] ?? field.typeHint}{field.dateRate > 0 && field.typeHint !== "date" ? <p className="text-xs text-foreground-500">日期格式 {Math.round(field.dateRate * 100)}%</p> : null}</td><td className="py-3">{field.missingCount}（{Math.round(field.missingCount / profile.rowCount * 100)}%）</td><td className="py-3">{field.distinctCount}</td><td className="py-3">{field.topValues?.length ? field.topValues.map((item) => `${item.value} (${item.count})`).join(" · ") : "无有效值"}</td><td className="py-3 text-foreground-500">{field.numericSummary ? <>最小 {field.numericSummary.min} · 中位 {field.numericSummary.median} · 最大 {field.numericSummary.max}<br />Q1 {field.numericSummary.q1} · Q3 {field.numericSummary.q3} · 疑似离群 {field.numericSummary.outlierCount}</> : field.typeHint === "number" ? "无有效数值" : "不适用（非数值字段）"}</td></tr>)}</tbody></table></div>
        </section>
        <section className={`${panel} space-y-3`}>
          <h2 className="font-semibold">实体与关联键候选</h2>
          <p className="text-xs text-foreground-500">仅按列名和重复度提示，图 JSON 的端点将按企业标识映射关联到本案例主表；覆盖和冲突以试运行结果为准。</p>
          {(profile.keyCandidates?.length ?? 0) === 0 ? <p className="text-sm text-foreground-500">未发现典型 ID/编号字段，请人工指定企业标识及关联字段。</p> : <div className="grid gap-2 sm:grid-cols-2">{profile.keyCandidates?.map((item) => <div key={item.field} className="rounded-md bg-background-50 p-3 text-sm"><strong>{item.field}</strong> · {item.kind === "entity_key" ? "实体标识候选" : "关联键候选"}<p className="mt-1 text-foreground-500">非缺失 {item.nonMissingCount} · 重复值 {item.duplicateValues}</p></div>)}</div>}
        </section>
        <section className={`${panel} space-y-3`}>
          <h2 className="font-semibold">疑似标签分布</h2>
          <p className="text-xs text-foreground-500">仅按字段名识别候选。类别比例来自本次文件，不能据此判断 0 或 1 的业务含义。</p>
          {(profile.labelCandidates?.length ?? 0) === 0 ? <p className="text-sm text-foreground-500">未发现典型标签字段名，需人工指定预测目标。</p> : <div className="grid gap-2 sm:grid-cols-2">{profile.labelCandidates?.map((item) => <div key={item.field} className="rounded-md bg-background-50 p-3 text-sm"><strong>{item.field}</strong><p className="mt-1">{item.values.map((value) => `${value.value}：${value.count}`).join(" · ") || "无有效值"}</p><p className="mt-1 text-foreground-500">不同值 {item.distinctCount} · 缺失 {item.missingCount}{item.minorityShare != null ? ` · 少数类 ${Math.round(item.minorityShare * 100)}%` : ""}</p></div>)}</div>}
        </section>
        <details className={panel}><summary className="cursor-pointer font-semibold">查看前 5 行数据预览</summary><div className="mt-3 overflow-x-auto"><table className="min-w-full text-left text-xs"><thead><tr>{profile.fields.map((field) => <th key={field.name} className="min-w-28 border-b border-background-200 px-2 py-2">{field.name}</th>)}</tr></thead><tbody>{profile.sampleRows.map((row, index) => <tr key={index}>{profile.fields.map((field) => <td key={field.name} className="max-w-64 break-words border-b border-background-200 px-2 py-2">{row[field.name] || "—"}</td>)}</tr>)}</tbody></table></div><p className="mt-2 text-xs text-foreground-500">预览中的长值仅展示前 80 个字符；原始文件不会被修改。</p></details>
        {preparation && <PreparationMappingEditor preparation={preparation} onSaved={setPreparation} disabled={busy || pendingFiles} />}
        {preparation && <PreparationConversionPanel preparationId={preparation.id} revision={preparation.updatedAt} disabled={busy || pendingFiles} />}
        {suggestion && <section className={`${panel} space-y-4`}><h2 className="font-semibold">智能体数据分析报告 · 待确认</h2><p className="text-xs text-foreground-500">报告依据本案例的主表统计和图文件清单生成；关系覆盖及属性冲突以试运行核验为准，未训练模型。</p><div className="space-y-3 text-sm leading-7"><ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml components={{ h2: ({ children }) => <h2 className="mt-4 text-base font-semibold">{children}</h2>, h3: ({ children }) => <h3 className="mt-3 font-semibold">{children}</h3>, ul: ({ children }) => <ul className="list-disc pl-5">{children}</ul>, ol: ({ children }) => <ol className="list-decimal pl-5">{children}</ol>, table: ({ children }) => <div className="overflow-x-auto"><table className="min-w-full border-collapse text-left">{children}</table></div>, th: ({ children }) => <th className="border border-background-300 p-2">{children}</th>, td: ({ children }) => <td className="border border-background-300 p-2">{children}</td>, a: ({ children, href }) => <a href={href} target="_blank" rel="noopener noreferrer" className="text-primary-400 underline">{children}</a>, img: ({ alt }) => <span>[图片：{alt || "无描述"}]</span> }}>{suggestion.reportMarkdown || suggestion.summary}</ReactMarkdown></div><details className="text-xs text-foreground-500"><summary className="cursor-pointer">查看工具调用记录（{suggestion.toolTrace?.length ?? 0} 次）</summary><ol className="mt-2 list-decimal pl-5">{suggestion.toolTrace?.map((tool, index) => <li key={index}>{tool}</li>)}</ol></details><details className="text-sm"><summary className="cursor-pointer font-medium">查看字段用途建议和核查清单</summary><div className="mt-3 space-y-2">{suggestion.suggestions.map((item) => <div key={item.field} className="rounded-md bg-background-50 p-3"><strong>{item.field}</strong> · {roleLabels[item.role] ?? item.role}<p className="text-foreground-500">{item.reason}</p></div>)}</div>{suggestion.questions.length > 0 && <ul className="mt-3 list-disc pl-5">{suggestion.questions.map((question, index) => <li key={index}>{question}</li>)}</ul>}{(suggestion.nextChecks?.length ?? 0) > 0 && <ol className="mt-3 list-decimal pl-5">{suggestion.nextChecks?.map((step, index) => <li key={index}>{step}</li>)}</ol>}</details></section>}
        <p className="text-sm text-foreground-500">分析、规则确认和转换都在数据准备中完成。训练文件准备齐全后，使用上方“训练包生成与交付”；已有标准数据包也可前往 <Link className="text-primary-400 underline" to="/modeling">模型训练工作台</Link>。</p>
      </>}
      </>}
    </div>
  );
}
