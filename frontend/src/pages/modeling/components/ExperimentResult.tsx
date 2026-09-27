import { useTranslation } from "react-i18next";
import type { ModelingExperiment } from "@/entities/modeling/model/types";
import Card from "@/shared/ui/Card";

interface ExperimentResultProps {
  experiment: ModelingExperiment;
}

function metric(value: number) {
  return value.toFixed(4);
}

export default function ExperimentResult({ experiment }: ExperimentResultProps) {
  const { t } = useTranslation();
  const test = experiment.metrics.test;
  const maxCoefficient = Math.max(
    ...experiment.coefficients.map((item) => Math.abs(item.coefficient)),
    1,
  );

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-primary-500/25 bg-primary-500/8 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs text-primary-400">{t("modeling.result.completed")}</p>
            <h2 className="mt-1 font-heading text-xl font-semibold text-foreground-950">
              {experiment.name}
            </h2>
          </div>
          <span className="rounded-full border border-primary-500/30 px-3 py-1 font-mono text-[11px] text-primary-400">
            logistic_regression · seed {experiment.configuration.seed}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[
          ["ROC-AUC", metric(test.rocAuc)],
          ["PR-AUC", metric(test.prAuc)],
          ["KS", metric(test.ks)],
          ["Brier", metric(test.brier)],
        ].map(([label, value]) => (
          <div key={label} className="rounded-lg border border-background-200 bg-background-100 p-4">
            <p className="font-mono text-xs text-foreground-500">{label}</p>
            <p className="mt-1 font-heading text-2xl font-semibold text-foreground-950">{value}</p>
            <p className="mt-1 text-[11px] text-foreground-500">{t("modeling.result.testSet")}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title={t("modeling.result.validation")} icon="ri-scales-3-line" bodyClassName="p-5">
          <div className="grid grid-cols-3 gap-3 text-center">
            {[
              ["Precision", test.precision],
              ["Recall", test.recall],
              ["F1", test.f1],
            ].map(([label, value]) => (
              <div key={String(label)} className="rounded-md bg-background-50 px-2 py-3">
                <p className="text-[11px] text-foreground-500">{label}</p>
                <p className="mt-1 font-mono text-lg text-foreground-950">{metric(Number(value))}</p>
              </div>
            ))}
          </div>
          <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
            {Object.entries(test.confusion).map(([key, value]) => (
              <div key={key} className="flex justify-between rounded-md border border-background-200 px-3 py-2">
                <span className="font-mono uppercase text-foreground-500">{key}</span>
                <strong className="text-foreground-900">{value}</strong>
              </div>
            ))}
          </div>
        </Card>

        <Card title={t("modeling.result.coefficients")} icon="ri-bar-chart-horizontal-line" bodyClassName="p-5">
          <div className="space-y-3">
            {experiment.coefficients.slice(0, 8).map((item) => (
              <div key={item.feature}>
                <div className="mb-1 flex justify-between gap-3 text-[11px]">
                  <span className="truncate font-mono text-foreground-700">{item.feature}</span>
                  <span className={item.coefficient >= 0 ? "text-danger-500" : "text-primary-400"}>
                    {item.coefficient >= 0 ? "+" : ""}{item.coefficient.toFixed(4)}
                  </span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-background-200">
                  <div
                    className={`h-full rounded-full ${item.coefficient >= 0 ? "bg-danger-500" : "bg-primary-500"}`}
                    style={{ width: `${Math.max(3, Math.abs(item.coefficient) / maxCoefficient * 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <p className="rounded-md border border-background-200 bg-background-100 px-4 py-3 text-xs leading-relaxed text-foreground-500">
        {t("modeling.result.disclaimer", {
          train: experiment.configuration.trainRows,
          test: experiment.configuration.testRows,
        })}
      </p>
    </div>
  );
}
