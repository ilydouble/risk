import { useTranslation } from "react-i18next";
import StatusPill from "@/entities/risk/ui/StatusPill";
import { EVAL_MODEL_VERSION } from "@/pages/model/lib/eval";
import type { EvalDashboard } from "@/entities/demo/model/types";

interface ModelHeaderProps {
  dashboard: EvalDashboard;
}

export default function ModelHeader({ dashboard }: ModelHeaderProps) {
  const { t } = useTranslation();
  const isCurrent = dashboard.modelVersion === EVAL_MODEL_VERSION;
  const meta: { label: string; value: string; icon: string }[] = [
    { label: t("model.header.trainedAt"), value: dashboard.trainedAt, icon: "ri-history-line" },
    { label: t("model.header.validatedAt"), value: dashboard.validatedAt, icon: "ri-calendar-check-line" },
    {
      label: t("model.header.dataset"),
      value: dashboard.datasetSize.toLocaleString("en-US"),
      icon: "ri-database-2-line",
    },
    {
      label: t("model.header.features"),
      value: t("model.header.featuresUnit", { count: dashboard.featureCount }),
      icon: "ri-stack-line",
    },
    {
      label: t("model.header.positiveRate"),
      value: `${(dashboard.positiveRate * 100).toFixed(1)}%`,
      icon: "ri-percent-line",
    },
    { label: t("model.header.split"), value: dashboard.splitRatio, icon: "ri-split-cells-horizontal" },
  ];

  return (
    <section className="animate-fade-up tech-grid overflow-hidden rounded-lg border border-background-200 bg-background-100">
      <div className="flex flex-col gap-5 p-5 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-start gap-4">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-primary-500/12 text-primary-400">
            <i className="ri-cpu-line text-2xl"></i>
          </span>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="font-heading text-lg font-semibold text-foreground-950">
                {t("model.header.title")}
              </h2>
              <span className="rounded-full border border-primary-400/40 bg-primary-500/12 px-2 py-0.5 font-mono text-[11px] text-primary-400">
                {dashboard.modelVersion}
              </span>
              {isCurrent ? (
                <StatusPill level="low" label={t("model.header.current")} size="sm" pulse />
              ) : (
                <span className="rounded-full border border-background-300 bg-background-200/60 px-2.5 py-0.5 text-[11px] text-foreground-600">
                  {t("model.header.history")}
                </span>
              )}
            </div>
            <p className="mt-2 max-w-2xl text-xs leading-relaxed text-foreground-500">
              {t("model.header.desc")}
            </p>
          </div>
        </div>

        <dl className="grid w-full grid-cols-2 gap-x-5 gap-y-3 sm:grid-cols-3 lg:w-auto lg:min-w-[440px]">
          {meta.map((item) => (
            <div key={item.label} className="flex items-start gap-2">
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center text-foreground-500">
                <i className={`${item.icon} text-[15px]`}></i>
              </span>
              <div className="min-w-0">
                <dt className="text-[10px] text-foreground-500">{item.label}</dt>
                <dd className="mt-0.5 truncate font-mono text-[12px] text-foreground-800">
                  {item.value}
                </dd>
              </div>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}