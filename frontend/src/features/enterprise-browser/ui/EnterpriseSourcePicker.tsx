import { Link } from "react-router-dom";
import type { useEnterpriseSource } from "../model/useEnterpriseSource";

const statuses = { ready: "已接入", pending: "校验/导入中", failed: "校验/导入失败", unavailable: "需重新上传" };
export default function EnterpriseSourcePicker({ source }: { source: ReturnType<typeof useEnterpriseSource> }) {
  return <section className="mb-5 rounded-lg border border-background-200 bg-background-100 p-4">
    <div className="flex flex-wrap items-center gap-3">
      <label htmlFor="enterprise-source" className="text-sm font-medium">当前数据源</label>
      <select id="enterprise-source" disabled={source.loading} value={source.mode === "sample" ? "sample" : source.datasetId}
        onChange={(event) => source.select(event.target.value)} className="min-w-48 flex-1 rounded-md border border-background-300 bg-background-50 px-3 py-2 text-sm">
        <optgroup label="共享演示数据"><option value="sample">新加坡演示数据 · 真实来源快照</option></optgroup>
        <optgroup label="我的上传数据 · 当前账号">
        {source.datasetId && !source.sources.some((item) => item.id === source.datasetId) && <option value={source.datasetId}>{source.datasetId}</option>}
        {source.sources.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.id.slice(0, 8)} · {statuses[item.importStatus]}</option>)}
        </optgroup>
      </select>
      <button type="button" onClick={source.retry} className="text-xs text-primary-400">刷新数据源</button>
      <Link className="text-xs text-primary-400" to="/data-prep">上传原始数据</Link>
      {source.sources.length < source.total && <button type="button" onClick={source.loadMore} className="text-xs text-primary-400">加载更多数据集</button>}
    </div>
    <div className="mt-3 rounded-md bg-background-50 p-3 text-xs leading-6" role="status">
      {source.mode === "sample" ? <><strong className="text-amber-600">当前：新加坡演示数据</strong><p>共享的真实来源统计快照与固定样本，仅用于演示和验证；不是实时数据或在线模型预测。演示记录不计入“我的上传数据”。</p></>
        : <><strong className="text-primary-400">当前：我的上传数据 · {source.selected?.name ?? source.datasetId}</strong><p>仅统计当前账号所选数据集，不包含共享演示数据。已有标签与模型预测分开；没有已保存预测时不展示演示评分补位。</p></>}
    </div>
    <p className="mt-2 text-xs text-foreground-500">概览和检索共用所选来源，来源切换时不合并统计。原始案例体检后保存；适配训练包校验并导入企业后才接入这两个页面。</p>
    {source.loading && <p role="status" className="mt-2 text-xs text-foreground-500">正在加载数据源…</p>}
    {source.error && <p role="alert" className="mt-2 text-xs text-danger-500">数据源加载失败：{source.error}</p>}
  </section>;
}
