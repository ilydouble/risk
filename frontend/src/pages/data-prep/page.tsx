import { useState } from "react";
import { Link } from "react-router-dom";
import { requestInspectData, requestSuggestMapping } from "@/features/data-prep/api/dataPrepApi";
import type { ResponseInspectData, ResponseSuggestMapping } from "@/shared/api/generated/schema";
import { handleApiError } from "@/shared/api/http";

const panel = "rounded-xl border border-background-200 bg-background-100 p-5";
const button = "rounded-md bg-primary-500 px-4 py-2 text-sm text-white disabled:opacity-50";

function fileBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1] ?? "");
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

export default function DataPrepPage() {
  const [file, setFile] = useState<File>();
  const [profile, setProfile] = useState<ResponseInspectData>();
  const [suggestion, setSuggestion] = useState<ResponseSuggestMapping>();
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
      setSuggestion(await requestSuggestMapping({ profile }));
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
            <div><h2 className="font-semibold">体检结果</h2><p className="text-sm text-foreground-500">{profile.rowCount} 行 · {profile.fields.length} 列 · {profile.duplicateRows} 行完全重复</p></div>
            <button className={button} disabled={busy} onClick={() => void suggest()}>{busy ? "分析中…" : "让智能体建议字段用途"}</button>
          </div>
          <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b border-background-200"><th className="py-2">字段</th><th>缺失</th><th>不同值</th><th>数值占比</th><th>常见值</th></tr></thead><tbody>{profile.fields.map((field) => <tr key={field.name} className="border-b border-background-200"><td className="py-2 font-medium">{field.name}</td><td>{field.missingCount}（{Math.round(field.missingCount / profile.rowCount * 100)}%）</td><td>{field.distinctCount}</td><td>{Math.round(field.numericRate * 100)}%</td><td className="max-w-64 truncate">{field.examples.join("、") || "—"}</td></tr>)}</tbody></table></div>
        </section>
        {suggestion && <section className={`${panel} space-y-3`}><h2 className="font-semibold">智能体建议 · 待确认</h2><p className="text-sm">{suggestion.summary}</p><div className="space-y-2">{suggestion.suggestions.map((item) => <div key={item.field} className="rounded-md bg-background-50 p-3 text-sm"><strong>{item.field}</strong> · {item.role}<p className="text-foreground-500">{item.reason}</p></div>)}</div>{suggestion.questions.length > 0 && <div><h3 className="font-medium">需要确认</h3><ul className="list-disc pl-5 text-sm">{suggestion.questions.map((question) => <li key={question}>{question}</li>)}</ul></div>}</section>}
        <p className="text-sm text-foreground-500">当前仅做分析；确认数据含义和构建训练集的功能仍在开发。已有标准数据包可前往 <Link className="text-primary-400 underline" to="/modeling">模型训练工作台</Link>。</p>
      </>}
    </div>
  );
}
