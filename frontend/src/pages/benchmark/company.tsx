import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import * as BenchmarkApi from "@/entities/benchmark/api/benchmarkApi";
import { useBenchmark } from "@/features/benchmark/model/useBenchmark";
import BenchmarkShell from "@/features/benchmark/ui/BenchmarkShell";
import BenchmarkState from "@/features/benchmark/ui/BenchmarkState";
import Card from "@/shared/ui/Card";

export default function BenchmarkCompany() {
  const { t } = useTranslation();
  const { id = "" } = useParams();
  const { data, loading, error, retry } = useBenchmark(`company:${id}`, () => BenchmarkApi.requestGetBenchmark({ id }));
  return <BenchmarkShell title={`${t("benchmark.profile")} · ${id}`}>
    <BenchmarkState loading={loading} error={error} retry={retry} />
    {data && !error && <>
      <div className="grid gap-4 md:grid-cols-3">
        <Card title={t("benchmark.probability")} bodyClassName="p-5"><strong className="font-heading text-3xl text-foreground-950">{(data.riskProbability * 100).toFixed(2)}%</strong></Card>
        <Card title={t("benchmark.demoScore")} bodyClassName="p-5"><strong className="font-heading text-3xl text-foreground-950">{data.creditScore}</strong><p className="mt-1 text-xs text-foreground-500">{t("benchmark.linearScore")}</p></Card>
        <Card title={t("benchmark.events")} bodyClassName="p-5"><strong className="font-heading text-3xl text-foreground-950">{data.eventCount}</strong></Card>
      </div>
      <div className="flex flex-wrap gap-2"><Link to={`/benchmark/score/${id}`} className="rounded-md bg-primary-500 px-4 py-2 text-sm text-background-50">{t("benchmark.explanation")}</Link><Link to={`/benchmark/graph/${id}`} className="rounded-md border border-background-300 px-4 py-2 text-sm text-foreground-800">{t("benchmark.graph")}</Link></div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title={t("benchmark.features")} subtitle={t("benchmark.featureNote")} bodyClassName="divide-y divide-background-200">{Object.entries(data.features).map(([name, value]) => <div key={name} className="flex justify-between gap-4 px-4 py-3 text-xs"><span className="text-foreground-600">{name}</span><span className="font-mono text-foreground-950">{value == null ? "—" : Number(value).toFixed(3)}</span></div>)}</Card>
        <Card title={t("benchmark.observed")} subtitle={t("benchmark.observedNote")} bodyClassName="p-5"><p className="text-sm text-foreground-800">{data.observedLabel === 1 ? t("benchmark.bankrupt") : t("benchmark.survived")}</p><p className="mt-3 text-xs text-foreground-500">{data.dataset} · {data.community}</p></Card>
      </div>
    </>}
  </BenchmarkShell>;
}
