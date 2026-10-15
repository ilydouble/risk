import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { requestGetPreparation, requestListPreparations } from "@/features/data-prep/api/dataPrepApi";
import { PreparationMappingEditor } from "@/features/data-prep/ui/PreparationMappingEditor";
import type { ResponsePreparation } from "@/shared/api/generated/schema";
import { handleApiError } from "@/shared/api/http";
import { box } from "./presentation";

export function PreparationHandoffPanel() {
  const [params, setParams] = useSearchParams();
  const id = params.get("preparation");
  const [items, setItems] = useState<ResponsePreparation[]>([]);
  const [source, setSource] = useState<ResponsePreparation>();
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    requestListPreparations({ workbenchOnly: true }).then(result => { if (active) setItems(result.items); })
      .catch(cause => { if (active) setError(handleApiError(cause)); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    let active = true;
    setSource(undefined);
    if (id) requestGetPreparation({ preparationId: id }).then(result => { if (active) setSource(result); })
      .catch(cause => { if (active) setError(handleApiError(cause)); });
    return () => { active = false; };
  }, [id]);
  return <>
    <section className={`${box} space-y-3`}>
      <h2 className="font-semibold">从数据准备继续 · 原文件与映射共用</h2>
      <p className="text-sm text-foreground-500">先在数据准备中分析原始字段、确认映射与转换方式，再在这里继续适配。无需再次上传同一份原始 CSV。</p>
      {items.length > 0 && <select aria-label="已移交的数据准备" value={id ?? ""} className="w-full rounded-md border border-background-300 bg-background-50 p-2 text-sm" onChange={event => setParams(previous => { const next = new URLSearchParams(previous); next.set("preparation", event.target.value); next.set("tab", "dataset"); return next; })}><option value="">选择已移交案例</option>{items.map(item => <option key={item.id} value={item.id}>{item.filename} · {item.profile.rowCount} 行 · {item.confirmed ? "映射已确认" : "映射待确认"}</option>)}</select>}
      <Link className="text-sm text-primary-400 underline" to="/data-prep">上传或分析原始数据、发现映射方式</Link>
      {source && <div className="space-y-2 rounded-md bg-background-50 p-3 text-sm"><p><strong>{source.filename}</strong> · {source.profile.rowCount} 行 · SHA-256 {source.profile.sha256}</p><p>状态：{source.confirmed ? "映射方案已确认，待模型适配" : "映射方案待确认"}</p><p className="text-foreground-500">下一步需按实际模型适配器准备特征、关系及独立划分。这份单表尚未转换成可训练数据包；不能凭字段名补造关系或划分。</p><Link className="text-primary-400 underline" to={`/data-prep?preparation=${encodeURIComponent(source.id)}`}>返回同一案例查看统计与完整报告</Link>{source.report && <details><summary className="cursor-pointer">已有分析报告</summary><p className="mt-2 whitespace-pre-wrap text-xs leading-6">{source.report.reportMarkdown || source.report.summary}</p></details>}</div>}
      {error && <p role="alert" className="text-sm text-red-500">{error}</p>}
    </section>
    {source && <PreparationMappingEditor preparation={source} onSaved={setSource} />}
  </>;
}
