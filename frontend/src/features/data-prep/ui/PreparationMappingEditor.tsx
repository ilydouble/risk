import { useEffect, useState } from "react";
import type { ResponsePreparation } from "@/shared/api/generated/schema";
import { handleApiError } from "@/shared/api/http";
import { requestExportPreparation, requestSavePreparationMapping } from "../api/dataPrepApi";

const roles = { identity: "企业标识", feature: "特征", label: "标签", relation: "关系字段", time: "时间/划分", ignore: "忽略", unknown: "待确认" };
const control = "w-full rounded-md border border-background-300 bg-background-50 p-2 text-xs disabled:opacity-50";

export function PreparationMappingEditor({ preparation, onSaved, disabled = false }: {
  preparation: ResponsePreparation;
  onSaved: (value: ResponsePreparation) => void;
  disabled?: boolean;
}) {
  const [mapping, setMapping] = useState(preparation.mapping);
  const [confirmed, setConfirmed] = useState(preparation.confirmed);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  useEffect(() => { setMapping(preparation.mapping); setConfirmed(preparation.confirmed); }, [preparation]);
  const blocked = busy || disabled;
  const change = (index: number, values: Partial<typeof mapping[number]>) => {
    setMapping(current => current.map((item, i) => i === index ? { ...item, ...values } : item));
    setConfirmed(false); setStatus("");
  };
  async function save() {
    setBusy(true); setError(""); setStatus("");
    try {
      const result = await requestSavePreparationMapping({ preparationId: preparation.id, mapping, confirmed, handoff: false });
      onSaved(result);
      setStatus(confirmed ? "映射方案已确认并保存。" : "映射草稿已保存。修改后需重新确认。");
    } catch (cause) {
      setError(handleApiError(cause, {
        DATA_PREP_MAPPING_INVALID: "请为每个字段明确用途，指定一个企业标识和至少一个特征，填写不重复的目标及转换方式，并解决“待确认”项。",
        DATA_PREP_NOT_FOUND: "这份准备记录不存在或无权访问，请重新选择。",
      }));
    } finally { setBusy(false); }
  }
  async function download() {
    setBusy(true); setError("");
    try {
      const result = await requestExportPreparation({ preparationId: preparation.id });
      const bytes = Uint8Array.from(atob(result.contentBase64), char => char.charCodeAt(0));
      const url = URL.createObjectURL(new Blob([bytes], { type: "application/zip" }));
      const anchor = document.createElement("a"); anchor.href = url; anchor.download = result.filename; anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (cause) { setError(handleApiError(cause)); }
    finally { setBusy(false); }
  }
  return <section className="space-y-4 rounded-xl border border-background-200 bg-background-100 p-5">
    <div><h2 className="font-semibold">字段映射与适配方案</h2><p className="mt-2 text-sm text-foreground-500">分析用于发现映射方式。请核对源字段对应的目标和处理规则；标识符保留前导零，标签需明确业务含义，关系需有来源依据。</p></div>
    <div className="overflow-x-auto"><table className="min-w-full text-left text-xs"><thead><tr><th className="min-w-36 p-2">源字段</th><th className="min-w-32 p-2">用途</th><th className="min-w-48 p-2">目标字段/结构</th><th className="min-w-64 p-2">转换方式与依据</th></tr></thead><tbody>
      {mapping.map((item, index) => <tr key={item.field} className="border-t border-background-200 align-top">
        <td className="p-2 font-medium">{item.field}</td>
        <td className="p-2"><select aria-label={`${item.field} 用途`} className={control} disabled={blocked} value={item.role} onChange={event => change(index, { role: event.target.value as typeof item.role })}>{Object.entries(roles).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></td>
        <td className="p-2"><input aria-label={`${item.field} 目标`} maxLength={128} className={control} disabled={blocked} value={item.target} placeholder="例如 enterprise.id / features.age" onChange={event => change(index, { target: event.target.value })} /></td>
        <td className="p-2"><textarea aria-label={`${item.field} 转换方式`} maxLength={500} rows={2} className={control} disabled={blocked} value={item.method} placeholder="例如保留文本；缺失值处理；0/1业务语义；关系构建依据" onChange={event => change(index, { method: event.target.value })} /><p className="mt-1 text-foreground-500">{item.reason}</p></td>
      </tr>)}
    </tbody></table></div>
    <label className="flex items-start gap-2 text-sm"><input type="checkbox" disabled={blocked} checked={confirmed} onChange={event => { setConfirmed(event.target.checked); setStatus(""); }} />我已核对字段含义、标签语义和转换方式，确认这份映射方案。</label>
    <p className="text-xs leading-6 text-foreground-500">这是一份适配方案，尚未执行转换。原文件、报告和映射保存在当前案例。完成转换与打包后，再将标准 ZIP 交付工作台。训练仍需满足模型适配器对关系数据、特征及训练/验证/测试划分的要求。</p>
    <div className="flex flex-wrap items-center gap-3">
      <button type="button" disabled={blocked} onClick={() => void save()} className="rounded-md border border-background-300 px-4 py-2 text-sm disabled:opacity-50">{busy ? "保存中…" : "保存映射方案"}</button>

      <button type="button" disabled={blocked} onClick={() => void download()} className="rounded-md border border-background-300 px-4 py-2 text-sm disabled:opacity-50">下载已保存的原文件与映射交付包</button>
      {status && <p role="status" className="text-sm text-foreground-500">{status}</p>}
    </div>
    {error && <p role="alert" className="text-sm text-red-500">{error}</p>}
  </section>;
}
