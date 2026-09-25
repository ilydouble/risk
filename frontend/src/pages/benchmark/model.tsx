import { useTranslation } from "react-i18next";
import * as BenchmarkApi from "@/entities/benchmark/api/benchmarkApi";
import { useBenchmark } from "@/features/benchmark/model/useBenchmark";
import BenchmarkShell from "@/features/benchmark/ui/BenchmarkShell";
import BenchmarkState from "@/features/benchmark/ui/BenchmarkState";
import Card from "@/shared/ui/Card";

export default function BenchmarkModel() {
  const { t } = useTranslation();
  const { data, loading, error, retry } = useBenchmark("model", async () => {
    const [card, evaluation] = await Promise.all([
      BenchmarkApi.requestModelCardBenchmark({}), BenchmarkApi.requestEvaluationBenchmark({}),
    ]);
    return { card, evaluation };
  });
  const { card, evaluation } = data ?? {};
  return <BenchmarkShell title={t("benchmark.model")}>
    <BenchmarkState loading={loading} error={error} retry={retry} />
    {card && evaluation && !error && <>
      <div className="grid gap-4 md:grid-cols-2"><Card title={card.model} subtitle={card.dataset} bodyClassName="space-y-3 p-5 text-sm text-foreground-700"><p>{t("benchmark.target")}: {card.targetDescription}</p><p>{t("benchmark.mode")}: {card.mode}</p><p>{t("benchmark.bestEpoch")}: {card.bestEpoch}</p><p>{t("benchmark.threshold")}: {(card.threshold * 100).toFixed(2)}%</p></Card><Card title={t("benchmark.inputSchema")} bodyClassName="space-y-2 p-5 text-xs text-foreground-700"><p>{t("benchmark.features")}: {card.featureNames.join(", ")}</p><p>{t("benchmark.relations")}: {card.relationNames.join(", ")}</p><p>{t("benchmark.hyperedges")}: {card.hyperedgeTypes.join(", ")}</p></Card></div>
      <Card title={t("benchmark.evaluation")} subtitle={t("benchmark.savedMetric")} bodyClassName="overflow-x-auto"><table className="w-full min-w-[620px] text-left text-xs"><thead className="bg-background-200/50 text-foreground-500"><tr><th className="px-4 py-3">{t("benchmark.split")}</th><th>n</th><th>ROC-AUC</th><th>PR-AUC</th><th>KS</th><th>Brier</th><th>F1</th></tr></thead><tbody>{(["train", "valid", "test"] as const).map((split) => { const m = evaluation.metrics[split]; return <tr key={split} className="border-t border-background-200 text-foreground-800"><td className="px-4 py-3 font-medium">{split}</td><td>{m.n}</td><td>{m.roc_auc?.toFixed(4) ?? "—"}</td><td>{m.pr_auc?.toFixed(4) ?? "—"}</td><td>{m.ks?.toFixed(4) ?? "—"}</td><td>{m.brier.toFixed(4)}</td><td>{m.f1.toFixed(4)}</td></tr>; })}</tbody></table></Card>
      <Card title={t("benchmark.limitations")} bodyClassName="space-y-2 p-5 text-sm leading-relaxed text-foreground-700"><p>{t("benchmark.limit1")}</p><p>{t("benchmark.limit2")}</p><p>{t("benchmark.limit3")}</p></Card>
    </>}
  </BenchmarkShell>;
}
