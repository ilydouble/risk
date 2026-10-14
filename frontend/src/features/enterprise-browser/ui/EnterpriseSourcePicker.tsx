import { Link } from "react-router-dom";
import type { useEnterpriseSource } from "../model/useEnterpriseSource";

const statuses = { ready: "已接入", pending: "校验/导入中", failed: "校验/导入失败", unavailable: "需重新上传" };
export default function EnterpriseSourcePicker({ source }: { source: ReturnType<typeof useEnterpriseSource> }) {
  return <section className="mb-5 rounded-lg border border-background-200 bg-background-100 p-4">
    <div className="flex flex-wrap items-center gap-3">
      <label htmlFor="enterprise-source" className="text-sm font-medium">当前数据集</label>
      <select id="enterprise-source" disabled={source.loading} value={source.mode === "sample" ? "sample" : source.datasetId}
        onChange={(event) => source.select(event.target.value)} className="min-w-48 flex-1 rounded-md border border-background-300 bg-background-50 px-3 py-2 text-sm">
        <option value="sample">新加坡样本 · 既有数据快照</option>
        {source.datasetId && !source.sources.some((item) => item.id === source.datasetId) && <option value={source.datasetId}>{source.datasetId}</option>}
        {source.sources.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.id.slice(0, 8)} · {statuses[item.importStatus]}</option>)}
      </select>
      <button type="button" onClick={source.retry} className="text-xs text-primary-400">刷新数据源</button>
      <Link className="text-xs text-primary-400" to="/modeling">上传数据</Link>
      {source.sources.length < source.total && <button type="button" onClick={source.loadMore} className="text-xs text-primary-400">加载更多数据集</button>}
    </div>
    <p className="mt-2 text-xs text-foreground-500">总览与企业检索共用所选数据集；上传校验通过后自动接入。数据按当前账号隔离。</p>
    {source.loading && <p role="status" className="mt-2 text-xs text-foreground-500">正在加载数据源…</p>}
    {source.error && <p role="alert" className="mt-2 text-xs text-danger-500">数据源加载失败：{source.error}</p>}
  </section>;
}
