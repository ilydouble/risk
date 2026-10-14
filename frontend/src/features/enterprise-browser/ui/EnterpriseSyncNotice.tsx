import { useState } from "react";
import { Link } from "react-router-dom";
import { requestImportEnterprises } from "@/entities/modeling/api/modelingApi";
import type { components } from "@/shared/api/generated/schema";
type EnterpriseSourceDTO = components["schemas"]["EnterpriseSourceDTO"];
import { handleApiError } from "@/shared/api/http";

export default function EnterpriseSyncNotice({ dataset, refresh }: { dataset: EnterpriseSourceDTO; refresh: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (dataset.importStatus === "ready") return null;
  async function retry() {
    setBusy(true); setError("");
    try { await requestImportEnterprises({ datasetId: dataset.id }); refresh(); }
    catch (cause) { setError(handleApiError(cause, { MODELING_ENTERPRISE_INVALID: "标准企业数据校验失败，请检查原数据。", MODELING_ENTERPRISE_UNAVAILABLE: "此数据集缺少企业产物，需要重新上传。", MODELING_DATASET_NOT_READY: "数据校验尚未完成。" })); }
    finally { setBusy(false); }
  }
  return <div className="rounded-lg border border-accent-500/30 bg-accent-500/10 p-4 text-sm">
    <p>{dataset.status === "failed" || dataset.status === "cancelled" ? "数据包校验失败或已取消，请返回工作台检查原因。" : dataset.importStatus === "unavailable" ? "此历史数据集未包含标准企业产物，请重新上传。" : dataset.importStatus === "failed" ? `企业导入失败：${dataset.importError ?? "未知错误"}。后台会重试，也可手动重试。` : "数据正在校验或导入，完成后总览与检索会自动更新。"}</p>
    {dataset.importStatus === "failed" && dataset.status === "completed" && <button type="button" disabled={busy} className="mt-3 text-xs text-primary-400" onClick={() => void retry()}>{busy ? "正在导入…" : "重试导入"}</button>}
    <Link className="ml-3 text-xs text-primary-400" to={`/modeling?dataset=${encodeURIComponent(dataset.id)}&tab=dataset`}>查看工作台</Link>
    {error && <p role="alert" className="mt-2 text-danger-500">{error}</p>}
  </div>;
}
