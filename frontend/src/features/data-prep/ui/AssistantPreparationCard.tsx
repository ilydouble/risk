import { Link } from "react-router-dom";
import type { ResponsePreparation } from "@/shared/api/generated/schema";
import { PreparationMappingEditor } from "./PreparationMappingEditor";
import { PreparationConversionPanel } from "./PreparationConversionPanel";

export function AssistantPreparationCard({ preparation, conversationId, disabled, onStart, onConvert, onSaved }: {
  preparation: ResponsePreparation;
  conversationId: string | null;
  disabled: boolean;
  onStart: () => void;
  onConvert: () => void;
  onSaved: (value: ResponsePreparation) => void;
}) {
  const unresolved = preparation.mapping.filter(item => item.role === "unknown" || (item.role !== "ignore" && (
    !item.target.trim() || !item.method.trim() || item.target.includes("待确认") || item.method.includes("待确认")
  )));
  return <section aria-label="当前数据准备案例" className="max-h-[40vh] overflow-y-auto border-b border-background-200 bg-primary-500/5 px-5 py-3">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="min-w-0"><h2 className="break-all text-sm font-semibold">当前案例：{preparation.filename}</h2>
        <p className="mt-1 text-xs text-foreground-500">{preparation.profile.rowCount} 条记录 · {preparation.profile.fields.length} 个字段 · {preparation.confirmed ? "原字段方案已确认" : `原字段方案为草稿 · ${unresolved.length} 个字段规则待完善`} · {preparation.report ? "已有分析报告" : "尚未生成分析报告"}</p>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-xs">
        <button disabled={disabled} onClick={onStart} className="rounded-lg bg-primary-500 px-3 py-2 text-white disabled:opacity-40">让助手梳理待确认问题</button>
        <Link className="text-primary-500 underline" to={`/data-prep?preparation=${encodeURIComponent(preparation.id)}${conversationId ? `&conversation=${encodeURIComponent(conversationId)}` : ""}`}>返回数据准备</Link>
      </div>
    </div>
    <details className="mt-3 text-xs">
      <summary className="cursor-pointer text-foreground-600">查看问题与映射方案 · 可修改并保存</summary>
      <div className="mt-3 space-y-3">
        {unresolved.length > 0 && <p className="text-foreground-500">待完善字段：{unresolved.map(item => item.field).join("、")}</p>}
        {Boolean(preparation.report?.questions.length) && <ul className="list-disc space-y-1 pl-5">{preparation.report?.questions.map((question, index) => <li key={index}>{question}</li>)}</ul>}
        <p className="leading-6 text-foreground-500">助手可保存可执行规则并试运行，结果在下方核验。修改原映射会使旧转换结果失效，须重新核对规则。</p>
        <PreparationMappingEditor preparation={preparation} onSaved={onSaved} disabled={disabled} />
      </div>
    </details>
    <PreparationConversionPanel preparationId={preparation.id} disabled={disabled} revision={preparation.updatedAt} onAsk={onConvert} />
  </section>;
}
