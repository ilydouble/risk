import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import * as BenchmarkApi from "@/entities/benchmark/api/benchmarkApi";
import { useBenchmark } from "@/features/benchmark/model/useBenchmark";
import BenchmarkShell from "@/features/benchmark/ui/BenchmarkShell";
import BenchmarkState from "@/features/benchmark/ui/BenchmarkState";
import Card from "@/shared/ui/Card";

export default function BenchmarkOverview() {
  const { t } = useTranslation();
  const { data, loading, error, retry } = useBenchmark("overview", () => BenchmarkApi.requestEvaluationBenchmark({}));
  const metric = data?.metrics.test;
  return <BenchmarkShell title={t("benchmark.title")}>
    <BenchmarkState loading={loading} error={error} retry={retry} />
    {data && !error && <>
      <div className="grid gap-4 md:grid-cols-3">
        <Card title={t("benchmark.companies")} icon="ri-building-2-line" bodyClassName="p-5"><strong className="font-heading text-3xl text-foreground-950">{data.companyCount}</strong><p className="mt-2 text-xs text-foreground-500">{data.dataset}</p></Card>
        <Card title="ROC-AUC" icon="ri-line-chart-line" bodyClassName="p-5"><strong className="font-heading text-3xl text-foreground-950">{metric?.roc_auc?.toFixed(4) ?? "—"}</strong><p className="mt-2 text-xs text-foreground-500">{t("benchmark.savedMetric")}</p></Card>
        <Card title="PR-AUC" icon="ri-pulse-line" bodyClassName="p-5"><strong className="font-heading text-3xl text-foreground-950">{metric?.pr_auc?.toFixed(4) ?? "—"}</strong><p className="mt-2 text-xs text-foreground-500">{t("benchmark.savedMetric")}</p></Card>
      </div>
      <Card title={t("benchmark.startHere")} icon="ri-compass-3-line" bodyClassName="p-5">
        <p className="max-w-2xl text-sm leading-relaxed text-foreground-700">{t("benchmark.intro")}</p>
        <div className="mt-5 flex flex-wrap gap-2">
          <Link to="/benchmark/search" className="rounded-md bg-primary-500 px-4 py-2 text-sm text-background-50 hover:bg-primary-600">{t("benchmark.search")}</Link>
          <Link to="/benchmark/company/C00010" className="rounded-md border border-background-300 px-4 py-2 text-sm text-foreground-800 hover:border-primary-400">C00010</Link>
          <Link to="/benchmark/model" className="rounded-md border border-background-300 px-4 py-2 text-sm text-foreground-800 hover:border-primary-400">{t("benchmark.model")}</Link>
        </div>
      </Card>
    </>}
  </BenchmarkShell>;
}
