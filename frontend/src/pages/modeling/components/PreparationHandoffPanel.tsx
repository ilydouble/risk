import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { requestGetPreparation } from "@/features/data-prep/api/dataPrepApi";
import type { ResponsePreparation } from "@/shared/api/generated/schema";
import { handleApiError } from "@/shared/api/http";
import { box } from "./presentation";

export function PreparationHandoffPanel() {
  const [params, setParams] = useSearchParams();
  const id = params.get("preparation");
  const [source, setSource] = useState<ResponsePreparation>();
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setSource(undefined); setError("");
    if (id) requestGetPreparation({ preparationId: id }).then(result => { if (active) setSource(result); })
      .catch(cause => { if (active) setError(handleApiError(cause)); });
    return () => { active = false; };
  }, [id]);
  return <section className={`${box} space-y-3`}>
    <h2 className="font-semibold">准备数据 → 交付标准包 → 工作台校验与实验</h2>
    <p className="text-sm text-foreground-500">智能体分析、字段映射和转换在独立的数据准备工具完成。工作台接收标准 ZIP，校验数据后开展训练与评估。</p>
    <Link className="text-sm text-primary-400 underline" to="/data-prep">打开数据准备工具</Link>
    {source && <div className="space-y-2 rounded-md bg-background-50 p-3 text-sm">
      <p><strong>本次上传关联案例：{source.filename}</strong></p>
      <p className="break-all text-xs text-foreground-500">来源 SHA-256：{source.profile.sha256}</p>
      <p>{source.confirmed ? "映射已确认，上传时封存来源快照。" : "映射待确认，请先返回数据准备完成确认，再上传关联包。"}</p>
      <Link className="text-primary-400 underline" to={`/data-prep/legacy?preparation=${encodeURIComponent(source.id)}`}>查看来源与修改方案</Link>
    </div>}
    {id && <button className="block text-xs text-primary-400 underline" onClick={() => setParams(previous => { const next = new URLSearchParams(previous); next.delete("preparation"); return next; })}>取消本次上传的案例关联</button>}
    {error && <p role="alert" className="text-sm text-red-500">{error}</p>}
  </section>;
}
