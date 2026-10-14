import { useState } from "react";
import { Link } from "react-router-dom";
import { requestInspectData, requestSuggestMapping } from "@/features/data-prep/api/dataPrepApi";
import { useAiModelConfig } from "@/features/ai-model-config/model/context";
import { useDataPrepSession } from "@/features/data-prep/model/context";
import { handleApiError } from "@/shared/api/http";

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
  const { file, profile, suggestion, setFile, setProfile, setSuggestion } = useDataPrepSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function inspect() {
    if (!file || busy) return;
    setBusy(true);
    setError("");
    setProfile(undefined);
    setSuggestion(undefined);
    try {
      setProfile(await requestInspectData({ filename: file.name, contentBase64: await fileBase64(file) }));
    } catch (cause) {
      setError(handleApiError(cause, {
        DATA_PREP_SIZE_INVALID: "请选择不超过 2 MiB 的 CSV 文件。",
        DATA_PREP_ENCODING_INVALID: "请将文件保存为 UTF-8 编码的 CSV。",
        DATA_PREP_FORMAT_UNSUPPORTED: "当前试用版仅支持 CSV 文件。",
        DATA_PREP_HEADER_INVALID: "表头为空、列名为空或超过 100 列。",
        DATA_PREP_HEADER_DUPLICATE: "表头存在重复列名，请先修改。",
        DATA_PREP_ROW_INVALID: "部分数据行的列数超过表头。",
        DATA_PREP_ROWS_EXCEEDED: "文件超过 50000 行，请先拆分。",
      }));
    } finally {
      setBusy(false);
    }
  }

  async function suggest() {
    if (!profile || busy) return;
    setBusy(true);
    setError("");
    try {
      setSuggestion(await requestSuggestMapping({ profile, connection: modelConfig.connection, maxTokens: modelConfig.maxTokens }));
    } catch (cause) {
      setError(handleApiError(cause, {
        CHAT_NOT_CONFIGURED: "智能分析需要先配置后端大模型。数据体检结果仍可查看。",
        CHAT_UNREACHABLE: "暂时无法连接大模型，请稍后重试。",
        DATA_PREP_SUGGESTION_INVALID: "大模型未返回有效字段建议，请重试。",
      }));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <header>
        <h1 className="text-2xl font-semibold text-foreground-950">数据准备</h1>
        <p className="mt-2 text-sm text-foreground-500">先检查真实数据，再决定如何关联企业和构建 RiskGNN+ 数据集。</p>
      </header>
      <div className={`${panel} flex flex-wrap items-center justify-between gap-3 text-sm`}>
        <span>字段建议使用：{modelConfig.custom ? modelConfig.model || "自定义模型（未填写）" : modelConfig.defaults?.model || "后端默认模型"}</span>
        <Link className="text-primary-400 underline" to="/settings/ai-model">配置智能体模型</Link>
      </div>
      <section className={`${panel} space-y-3`}>
        <h2 className="font-semibold">上传一张表进行体检</h2>
        <p className="text-sm text-foreground-500">试用版支持 UTF-8 CSV，最多 2 MiB、50000 行。分析结果只在当前页面展示，刷新后清空。</p>
        <input aria-label="选择 CSV 文件" type="file" accept=".csv,text/csv" disabled={busy} onChange={(event) => { setFile(event.target.files?.[0]); setProfile(undefined); setSuggestion(undefined); }} />
        <div><button className={button} disabled={!file || busy} onClick={() => void inspect()}>{busy ? "分析中…" : "开始体检"}</button></div>
      </section>
      {error && <p role="alert" className="text-sm text-red-500">{error}</p>}
      {profile && <>
        <section className={`${panel} space-y-3`}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div><h2 className="font-semibold">体检结果</h2><p className="text-sm text-foreground-500">统计基于整份文件；类型、键和异常只是待核对线索。</p></div>
            <button className={button} disabled={busy || (modelConfig.custom && (!modelConfig.url.trim() || !modelConfig.model.trim()))} onClick={() => void suggest()}>{busy ? "分析中…" : "让智能体建议字段用途"}</button>
          </div>
          <div className="grid gap-3 sm:grid-cols-4">
            {[
              ["记录", profile.rowCount],
              ["字段", profile.fields.length],
              ["含缺失值的记录", profile.rowsWithMissing],
              ["完全重复记录", profile.duplicateRows],
            ].map(([label, value]) => <div key={label} className="rounded-lg bg-background-50 p-3"><p className="text-xs text-foreground-500">{label}</p><p className="mt-1 text-xl font-semibold">{value}</p></div>)}
          </div>
          <p className="text-xs text-foreground-500">文件 SHA-256：<span className="break-all font-mono">{profile.sha256}</span> · 仅用于核对本次文件版本</p>
        </section>
        <section className={`${panel} space-y-3`}>
          <h2 className="font-semibold">数据质量线索 · {profile.issues?.length ?? 0} 项</h2>
          <p className="text-xs text-foreground-500">“未知”、空串、null、n/a 等按缺失统计；疑似离群值按四分位距筛出，不能直接认定为错误。</p>
          {(profile.issues?.length ?? 0) === 0 ? <p className="text-sm text-foreground-500">当前规则未发现明显问题，仍需核对字段语义和取值口径。</p> :
            <div className="grid gap-2 sm:grid-cols-2">{profile.issues?.map((item, index) => <div key={`${item.code}-${item.field ?? "row"}-${index}`} className="rounded-md border border-amber-500/20 bg-amber-500/5 p-3 text-sm"><strong>{item.field || "整表"}</strong> · {item.count} 处<p className="mt-1 text-foreground-500">{item.message}</p></div>)}</div>}
        </section>
        <section className={`${panel} space-y-3`}>
          <h2 className="font-semibold">字段画像</h2>
          <p className="text-xs text-foreground-500">标识列保持文本，尤其是含前导零的企业编号；常见值显示出现次数。</p>
          <div className="overflow-x-auto"><table className="min-w-full text-left text-sm"><thead><tr className="border-b border-background-200"><th className="min-w-36 py-2">字段</th><th className="min-w-28">类型线索</th><th className="min-w-28">缺失</th><th className="min-w-24">不同值</th><th className="min-w-64">常见值</th><th className="min-w-72">数值分布</th></tr></thead><tbody>{profile.fields.map((field) => <tr key={field.name} className="border-b border-background-200 align-top"><td className="py-3 font-medium">{field.name}</td><td className="py-3">{typeLabels[field.typeHint] ?? field.typeHint}{field.dateRate > 0 && field.typeHint !== "date" ? <p className="text-xs text-foreground-500">日期格式 {Math.round(field.dateRate * 100)}%</p> : null}</td><td className="py-3">{field.missingCount}（{Math.round(field.missingCount / profile.rowCount * 100)}%）</td><td className="py-3">{field.distinctCount}</td><td className="py-3">{field.topValues?.length ? field.topValues.map((item) => `${item.value} (${item.count})`).join(" · ") : "—"}</td><td className="py-3 text-foreground-500">{field.numericSummary ? <>最小 {field.numericSummary.min} · 中位 {field.numericSummary.median} · 最大 {field.numericSummary.max}<br />Q1 {field.numericSummary.q1} · Q3 {field.numericSummary.q3} · 疑似离群 {field.numericSummary.outlierCount}</> : "—"}</td></tr>)}</tbody></table></div>
        </section>
        <section className={`${panel} space-y-3`}>
          <h2 className="font-semibold">实体与关联键候选</h2>
          <p className="text-xs text-foreground-500">仅按列名和重复度提示，单张表无法验证外键是否能关联到系统企业表；需要目标表和业务口径确认。</p>
          {(profile.keyCandidates?.length ?? 0) === 0 ? <p className="text-sm text-foreground-500">未发现典型 ID/编号字段，请人工指定企业标识及关联字段。</p> : <div className="grid gap-2 sm:grid-cols-2">{profile.keyCandidates?.map((item) => <div key={item.field} className="rounded-md bg-background-50 p-3 text-sm"><strong>{item.field}</strong> · {item.kind === "entity_key" ? "实体标识候选" : "关联键候选"}<p className="mt-1 text-foreground-500">非缺失 {item.nonMissingCount} · 重复值 {item.duplicateValues}</p></div>)}</div>}
        </section>
        <section className={`${panel} space-y-3`}>
          <h2 className="font-semibold">疑似标签分布</h2>
          <p className="text-xs text-foreground-500">仅按字段名识别候选。类别比例来自本次文件，不能据此判断 0 或 1 的业务含义。</p>
          {(profile.labelCandidates?.length ?? 0) === 0 ? <p className="text-sm text-foreground-500">未发现典型标签字段名，需人工指定预测目标。</p> : <div className="grid gap-2 sm:grid-cols-2">{profile.labelCandidates?.map((item) => <div key={item.field} className="rounded-md bg-background-50 p-3 text-sm"><strong>{item.field}</strong><p className="mt-1">{item.values.map((value) => `${value.value}：${value.count}`).join(" · ") || "无有效值"}</p><p className="mt-1 text-foreground-500">不同值 {item.distinctCount} · 缺失 {item.missingCount}{item.minorityShare != null ? ` · 少数类 ${Math.round(item.minorityShare * 100)}%` : ""}</p></div>)}</div>}
        </section>
        <details className={panel}><summary className="cursor-pointer font-semibold">查看前 5 行数据预览</summary><div className="mt-3 overflow-x-auto"><table className="min-w-full text-left text-xs"><thead><tr>{profile.fields.map((field) => <th key={field.name} className="min-w-28 border-b border-background-200 px-2 py-2">{field.name}</th>)}</tr></thead><tbody>{profile.sampleRows.map((row, index) => <tr key={index}>{profile.fields.map((field) => <td key={field.name} className="max-w-64 break-words border-b border-background-200 px-2 py-2">{row[field.name] || "—"}</td>)}</tr>)}</tbody></table></div><p className="mt-2 text-xs text-foreground-500">预览中的长值仅展示前 80 个字符；原始文件不会被修改。</p></details>
        {suggestion && <section className={`${panel} space-y-3`}><h2 className="font-semibold">智能体分析 · 待确认</h2><p className="text-sm">{suggestion.summary}</p>{(suggestion.qualityFindings?.length ?? 0) > 0 && <div><h3 className="font-medium">质量与训练风险</h3><ul className="mt-2 list-disc space-y-1 pl-5 text-sm">{suggestion.qualityFindings?.map((finding, index) => <li key={index}>{finding}</li>)}</ul></div>}<div className="space-y-2">{suggestion.suggestions.map((item) => <div key={item.field} className="rounded-md bg-background-50 p-3 text-sm"><strong>{item.field}</strong> · {roleLabels[item.role] ?? item.role}<p className="text-foreground-500">{item.reason}</p></div>)}</div>{suggestion.questions.length > 0 && <div><h3 className="font-medium">需要确认</h3><ul className="list-disc pl-5 text-sm">{suggestion.questions.map((question, index) => <li key={index}>{question}</li>)}</ul></div>}{(suggestion.nextChecks?.length ?? 0) > 0 && <div><h3 className="font-medium">建议的下一步核查</h3><ol className="mt-2 list-decimal space-y-1 pl-5 text-sm">{suggestion.nextChecks?.map((step, index) => <li key={index}>{step}</li>)}</ol></div>}</section>}
        <p className="text-sm text-foreground-500">当前仅做分析；确认数据含义和构建训练集的功能仍在开发。已有标准数据包可前往 <Link className="text-primary-400 underline" to="/modeling">模型训练工作台</Link>。</p>
      </>}
    </div>
  );
}
