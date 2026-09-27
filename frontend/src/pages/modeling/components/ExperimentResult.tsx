import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { resultsOf, type ModelingExperiment } from "@/entities/modeling/model/types";
import Card from "@/shared/ui/Card";

interface ExperimentResultProps {
  experiment: ModelingExperiment;
}

const metric = (value: number) => value.toFixed(4);

export default function ExperimentResult({ experiment }: ExperimentResultProps) {
  const { t } = useTranslation();
  const results = useMemo(() => resultsOf(experiment), [experiment]);
  const profile = results.trainingProfile;
  const variants = useMemo(() => results.variants ?? [], [results]);
  const [selectedName, setSelectedName] = useState(variants[0]?.name ?? "");
  useEffect(() => setSelectedName(variants[0]?.name ?? ""), [experiment.id, variants]);
  const selected = useMemo(
    () => variants.find((item) => item.name === selectedName) ?? variants[0],
    [selectedName, variants],
  );

  if (experiment.status !== "completed") {
    const progress = Number(experiment.progress.percent ?? 0);
    return (
      <Card title={experiment.name} icon="ri-loader-4-line" bodyClassName="p-5">
        <div className="flex items-center justify-between text-xs text-foreground-500">
          <span>{experiment.error ?? String(experiment.progress.stage ?? experiment.status)}</span>
          <span>{progress}%</span>
        </div>
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-background-200">
          <div className={`h-full ${experiment.status === "failed" ? "bg-danger-500" : "bg-primary-500"}`} style={{ width: `${progress}%` }} />
        </div>
      </Card>
    );
  }
  if (!selected) return null;

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-primary-500/25 bg-primary-500/8 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div><p className="text-xs text-primary-400">{results.modelFamily ?? "RiskGNN-v1"} · {t("modeling.result.completed")}</p><h2 className="mt-1 font-heading text-xl font-semibold text-foreground-950">{experiment.name}</h2><p className="mt-1 text-xs text-foreground-500">{results.targetName} · {results.targetDefinition}</p></div>
          <span className="rounded-full border border-primary-500/30 px-3 py-1 font-mono text-[11px] text-primary-400">{t(`modeling.task.${results.taskType}`)}</span>
        </div>
      </div>

      <Card title={t("modeling.result.profile.title")} icon="ri-file-list-3-line" bodyClassName="p-5">
        {profile ? (
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {[
                [t("modeling.result.profile.dataset"), profile.dataset.datasetName],
                [t("modeling.result.profile.samples"), profile.dataset.sampleCount.toLocaleString()],
                [t("modeling.result.profile.entities"), profile.dataset.entityCount.toLocaleString()],
                [t("modeling.result.profile.features"), profile.features.selected.length.toString()],
                [t("modeling.result.profile.relations"), profile.graph.relations.rows.toLocaleString()],
                [t("modeling.result.profile.hyperedges"), profile.graph.hyperedges.count.toLocaleString()],
                [t("modeling.result.profile.seed"), profile.training.seed.toString()],
                [t("modeling.result.profile.fingerprint"), profile.dataset.bundleSha256.slice(0, 12)],
              ].map(([label, value]) => (
                <div key={label} className="rounded-md bg-background-50 px-3 py-3">
                  <p className="text-[11px] text-foreground-500">{label}</p>
                  <p className="mt-1 truncate font-mono text-sm font-semibold text-foreground-900" title={value}>{value}</p>
                </div>
              ))}
            </div>
            <div className="rounded-md border border-primary-500/25 bg-primary-500/8 px-4 py-3">
              <p className="text-xs font-semibold text-primary-500">{t("modeling.result.profile.independent")}</p>
              <p className="mt-1 text-xs leading-relaxed text-foreground-600">{t("modeling.result.profile.independentDescription")}</p>
            </div>
            <p className="font-mono text-[11px] text-foreground-500">
              {profile.provenance.coreImplementation} · {profile.provenance.codeVersion} · {profile.provenance.artifactFormat}
            </p>
            <details className="rounded-md border border-background-200 bg-background-50">
              <summary className="cursor-pointer px-4 py-3 text-xs font-semibold text-foreground-700">
                {t("modeling.result.profile.fullProfile")}
              </summary>
              <pre className="max-h-96 overflow-auto border-t border-background-200 p-4 font-mono text-[11px] leading-relaxed text-foreground-600">
                {JSON.stringify(profile, null, 2)}
              </pre>
            </details>
          </div>
        ) : (
          <p className="text-xs text-foreground-500">{t("modeling.result.profile.legacyUnavailable")}</p>
        )}
      </Card>

      <Card title={t("modeling.result.comparison")} icon="ri-scales-3-line" bodyClassName="overflow-x-auto">
        <table className="w-full min-w-[720px] text-left text-xs">
          <thead className="border-b border-background-200 bg-background-50 text-foreground-500"><tr><th className="px-4 py-2.5">{t("modeling.result.configuration")}</th><th>ROC-AUC</th><th>PR-AUC</th><th>KS</th><th>Brier</th><th>F1</th><th>{t("modeling.result.duration")}</th></tr></thead>
          <tbody>{variants.map((variant) => <tr key={variant.name} onClick={() => setSelectedName(variant.name)} className={`cursor-pointer border-b border-background-200/60 ${selected.name === variant.name ? "bg-primary-500/8" : "hover:bg-background-50"}`}><td className="px-4 py-3 font-semibold text-foreground-900">{t(`modeling.variant.${variant.name}`)}</td><td>{metric(variant.metrics.test.rocAuc)}</td><td>{metric(variant.metrics.test.prAuc)}</td><td>{metric(variant.metrics.test.ks)}</td><td>{metric(variant.metrics.test.brier)}</td><td>{metric(variant.metrics.test.f1)}</td><td>{variant.durationSeconds.toFixed(1)}s</td></tr>)}</tbody>
        </table>
      </Card>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[["ROC-AUC", selected.metrics.test.rocAuc], ["PR-AUC", selected.metrics.test.prAuc], ["KS", selected.metrics.test.ks], ["Brier", selected.metrics.test.brier]].map(([label, value]) => <div key={String(label)} className="rounded-lg border border-background-200 bg-background-100 p-4"><p className="font-mono text-xs text-foreground-500">{label}</p><p className="mt-1 font-heading text-2xl font-semibold text-foreground-950">{metric(Number(value))}</p><p className="mt-1 text-[11px] text-foreground-500">test · {t(`modeling.variant.${selected.name}`)}</p></div>)}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title={t("modeling.result.threshold")} icon="ri-dashboard-3-line" bodyClassName="p-5">
          <div className="grid grid-cols-3 gap-3 text-center">{[["Precision", selected.metrics.test.precision], ["Recall", selected.metrics.test.recall], ["F1", selected.metrics.test.f1]].map(([label, value]) => <div key={String(label)} className="rounded-md bg-background-50 px-2 py-3"><p className="text-[11px] text-foreground-500">{label}</p><p className="mt-1 font-mono text-lg text-foreground-950">{metric(Number(value))}</p></div>)}</div>
          <p className="mt-4 text-xs text-foreground-500">validation threshold · {selected.metrics.validation.threshold.toFixed(4)}</p>
        </Card>
        <Card title={t("modeling.result.explainability")} icon="ri-bar-chart-horizontal-line" bodyClassName="p-5">
          {selected.explainability.items ? <div className="space-y-2">{selected.explainability.items.slice(0, 10).map((item) => <div key={item.feature} className="flex justify-between gap-3 text-xs"><span className="truncate font-mono text-foreground-700">{item.feature}</span><b className={item.value >= 0 ? "text-danger-500" : "text-primary-400"}>{item.value.toFixed(4)}</b></div>)}</div> : <div className="space-y-2 text-xs text-foreground-700"><p>{t("modeling.result.contagionGate")}: <b>{selected.explainability.contagionRiskWeight?.toFixed(4) ?? "—"}</b></p><p>{t("modeling.result.hyperWeights")}: <b className="font-mono">{selected.explainability.hyperedgeTypeWeights?.map((value) => value.toFixed(3)).join(" / ") || "—"}</b></p></div>}
        </Card>
      </div>

      <p className="rounded-md border border-warning-500/25 bg-warning-500/8 px-4 py-3 text-xs leading-relaxed text-warning-700">{results.disclaimer}</p>
    </div>
  );
}
