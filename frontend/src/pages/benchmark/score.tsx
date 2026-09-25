import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import * as BenchmarkApi from "@/entities/benchmark/api/benchmarkApi";
import { useBenchmark } from "@/features/benchmark/model/useBenchmark";
import BenchmarkShell from "@/features/benchmark/ui/BenchmarkShell";
import BenchmarkState from "@/features/benchmark/ui/BenchmarkState";
import Card from "@/shared/ui/Card";

export default function BenchmarkScore() {
  const { t } = useTranslation();
  const { id = "" } = useParams();
  const { data, loading, error, retry } = useBenchmark(`score:${id}`, async () => {
    const [prediction, explanation] = await Promise.all([
      BenchmarkApi.requestPredictBenchmark({ companyIds: [id] }),
      BenchmarkApi.requestExplainBenchmark({ id }),
    ]);
    return { prediction, explanation };
  });
  const score = data?.prediction.predictions[0];
  const explanation = data?.explanation;
  return <BenchmarkShell title={`${t("benchmark.explanation")} · ${id}`}>
    <BenchmarkState loading={loading} error={error} retry={retry} />
    {score && explanation && !error && <>
      <div className="grid gap-4 md:grid-cols-3">
        <Card title={t("benchmark.probability")} bodyClassName="p-5"><strong className="font-heading text-3xl text-foreground-950">{(score.riskProbability * 100).toFixed(2)}%</strong></Card>
        <Card title={t("benchmark.demoScore")} bodyClassName="p-5"><strong className="font-heading text-3xl text-foreground-950">{score.creditScore}</strong><p className="mt-1 text-xs text-foreground-500">{t("benchmark.linearScore")}</p></Card>
        <Card title={t("benchmark.threshold")} bodyClassName="p-5"><strong className="font-heading text-3xl text-foreground-950">{(data.prediction.threshold * 100).toFixed(2)}%</strong><p className="mt-1 text-xs text-foreground-500">{t("benchmark.predictedClass", { value: score.predictedLabel })}</p></Card>
      </div>
      <Card title={t("benchmark.explanation")} subtitle={t("benchmark.explanationNote")} bodyClassName="divide-y divide-background-200">
        {explanation.features.map((feature) => <div key={feature.feature} className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm"><span className="min-w-48 text-foreground-800">{feature.feature}</span><span className="font-mono text-xs text-foreground-500">{t("benchmark.value")}: {feature.value?.toFixed(3) ?? "—"}</span><span className={`ml-auto font-mono text-xs ${feature.probability_delta >= 0 ? "text-accent-400" : "text-primary-400"}`}>{feature.probability_delta >= 0 ? "+" : ""}{(feature.probability_delta * 100).toFixed(2)} pp</span></div>)}
      </Card>
      <p className="text-xs text-foreground-500">{t("benchmark.explanationLimit")}</p>
      <div className="flex gap-2"><Link to={`/benchmark/company/${id}`} className="rounded-md border border-background-300 px-4 py-2 text-sm text-foreground-800">{t("benchmark.profile")}</Link><Link to={`/benchmark/graph/${id}`} className="rounded-md border border-background-300 px-4 py-2 text-sm text-foreground-800">{t("benchmark.graph")}</Link></div>
    </>}
  </BenchmarkShell>;
}
