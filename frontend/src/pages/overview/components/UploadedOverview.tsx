import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { requestEnterpriseOverview } from "@/entities/modeling/api/modelingApi";
import { displayEnterpriseValue, enterpriseLink, enterpriseName } from "@/entities/modeling/lib/enterpriseDisplay";
import EnterpriseSyncNotice from "@/features/enterprise-browser/ui/EnterpriseSyncNotice";
import type { ResponseEnterpriseOverview } from "@/shared/api/generated/schema";
import { handleApiError } from "@/shared/api/http";
import Card from "@/shared/ui/Card";
import StatCard from "@/shared/ui/StatCard";

export default function UploadedOverview({ datasetId, onImported }: { datasetId: string; onImported: () => void }) {
  const [data, setData] = useState<ResponseEnterpriseOverview>();
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const response = await requestEnterpriseOverview({ datasetId });
        if (!active) return;
        setData(response); setError("");
        if (response.dataset.importStatus === "pending" || response.dataset.importStatus === "failed") timer = setTimeout(() => void load(), 5000);
      } catch (cause) { if (active) setError(handleApiError(cause)); }
    }
    void load();
    return () => { active = false; clearTimeout(timer); };
  }, [datasetId, revision]);
  const reload = () => { setRevision((value) => value + 1); onImported(); };
  if (error) return <div role="alert" className="rounded-lg border border-danger-500/30 p-5 text-sm">{error}<button type="button" className="ml-3 text-primary-400" onClick={reload}>重试</button></div>;
  if (!data) return <p role="status" className="p-5 text-sm text-foreground-500">正在汇总所选数据集…</p>;
  const counts = data.dataset.counts;
  const charts = [{ name: "标签 0", count: data.labels.negative }, { name: "标签 1", count: data.labels.positive }, { name: "未标注", count: data.labels.unlabeled }];
  const searchLink = `/search?source=uploaded&dataset=${encodeURIComponent(datasetId)}`;
  return <div className="space-y-5">
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div><h1 className="text-2xl font-semibold">数据总览 · {data.dataset.name}</h1><p className="mt-2 text-xs text-foreground-500">数据集 ID：{datasetId} · 以下为导入数据统计，标签与模型预测分开展示。</p></div>
      <div className="flex gap-3 text-xs text-primary-400"><button type="button" onClick={reload}>刷新统计</button><Link to={searchLink}>检索本数据集企业 →</Link></div>
    </header>
    <EnterpriseSyncNotice dataset={data.dataset} refresh={reload} />
    {data.dataset.importStatus === "ready" && <>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        {[ ["企业", counts.company ?? 0, "ri-building-2-line"], ["人物", counts.person ?? 0, "ri-user-line"], ["普通关系", counts.edge ?? 0, "ri-share-line"], ["超边", counts.hyperedge ?? 0, "ri-group-line"], ["事件", counts.event ?? 0, "ri-calendar-event-line"] ].map(([label, count, icon]) => <StatCard key={String(label)} icon={String(icon)} label={String(label)} value={Number(count).toLocaleString()} delta="标准数据全量记录" tone="primary" />)}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="已有标签分布" subtitle="标签 0/1 的业务含义由当前数据集定义；未标注不视为负例。" icon="ri-bar-chart-line">
          <div className="h-64 p-4"><ResponsiveContainer width="100%" height="100%"><BarChart data={charts}><CartesianGrid opacity={0.15} strokeDasharray="3 3" /><XAxis dataKey="name" /><YAxis allowDecimals={false} /><Tooltip /><Bar dataKey="count" name="企业数" fill="#3b82f6" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div>
        </Card>
        <Card title="数据与预测口径" icon="ri-information-line" bodyClassName="space-y-3 p-5 text-sm leading-7">
          <p>目标定义：<span className="break-words">{displayEnterpriseValue(data.target)}</span></p>
          <p>企业、人物、关系和事件均来自所选数据集，节点及引用保留各自快照范围。</p>
          <p>已登记模型 {data.models.length} 个。模型预测需训练并登记后运行；主分类概率未经校准。</p>
          <Link to={`/modeling?dataset=${encodeURIComponent(datasetId)}&tab=dataset`} className="text-primary-400">打开该数据集工作台 →</Link>
        </Card>
      </div>
      <Card title="已登记模型与已有预测" subtitle="每行对应一个模型；同一企业在不同模型中的预测分别统计。" icon="ri-cpu-line" bodyClassName="overflow-x-auto p-4">
        <table className="w-full text-left text-xs"><thead><tr>{["模型", "已预测企业数", "预测类别 1", "平均主分类概率", "平均不确定性"].map((name) => <th key={name} className="border-b border-background-200 p-3">{name}</th>)}</tr></thead><tbody>{data.models.map((model) => <tr key={model.id}><td className="p-3"><Link className="text-primary-400" to={`/modeling?tab=model&model=${encodeURIComponent(model.id)}`}>{model.name}</Link><p className="mt-1 font-mono text-[10px] text-foreground-500">{model.id}</p></td><td className="p-3">{model.predictionCount}</td><td className="p-3">{model.positiveCount}</td><td className="p-3">{model.averageProbability == null ? "—" : `${(model.averageProbability * 100).toFixed(2)}%`}</td><td className="p-3">{model.averageUncertainty == null ? "—" : `${(model.averageUncertainty * 100).toFixed(2)}%`}</td></tr>)}</tbody></table>
        {data.models.length === 0 && <p className="py-6 text-center text-sm text-foreground-500">尚未登记模型；可先浏览和检索企业数据。</p>}
      </Card>
      <Card title="企业预览" subtitle="按原始记录顺序显示前8家；可在企业检索中浏览全量。" icon="ri-table-line" bodyClassName="p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{data.companies.map((company) => <Link key={company.sequence} to={enterpriseLink(datasetId, company.nodeId!)} className="rounded-lg border border-background-200 p-3 hover:border-primary-400"><p className="truncate text-sm font-medium">{enterpriseName(company)}</p><p className="mt-2 break-all font-mono text-[10px] text-foreground-500">{company.nodeId}</p><p className="mt-2 text-xs text-foreground-500">快照：{company.snapshot} · 标签：{displayEnterpriseValue(company.data.label)}</p></Link>)}</div>
        {data.companies.length === 0 && <p className="py-6 text-center text-sm text-foreground-500">此数据集中没有企业记录。</p>}
      </Card>
    </>}
  </div>;
}
