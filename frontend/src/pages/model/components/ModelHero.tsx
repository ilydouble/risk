import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import StatusPill from "@/entities/risk/ui/StatusPill";
import { modelIdentity } from "@/features/demo-scenarios/model/fixtures/modelCard";
import { modelMetrics } from "@/features/demo-scenarios/model/fixtures/overview";
import { useLang } from "@/shared/lib/useLang";

export default function ModelHero() {
  const { t } = useTranslation();
  const { pick } = useLang();

  const meta: { label: string; value: string; icon: string }[] = [
    { label: t("model.hero.owner"), value: pick(modelIdentity.owner, modelIdentity.ownerEn), icon: "ri-team-line" },
    { label: t("model.hero.releasedAt"), value: modelIdentity.releasedAt, icon: "ri-calendar-check-line" },
    { label: t("model.hero.validatedAt"), value: modelIdentity.validatedAt, icon: "ri-shield-check-line" },
  ];

  return (
    <section className="animate-fade-up tech-grid overflow-hidden rounded-lg border border-background-200 bg-background-100">
      <div className="flex flex-col gap-5 p-5 xl:flex-row xl:items-start xl:justify-between">
        <div className="flex min-w-0 items-start gap-4">
          <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-lg bg-primary-500/12 text-primary-400">
            <i className="ri-cpu-line text-2xl"></i>
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2.5">
              <h2 className="font-heading text-xl font-semibold text-foreground-950">
                {pick(modelIdentity.name, modelIdentity.nameEn)}
              </h2>
              <span className="rounded-full border border-primary-400/40 bg-primary-500/12 px-2 py-0.5 font-mono text-[11px] text-primary-400">
                {modelIdentity.version}
              </span>
              <StatusPill
                level={modelIdentity.status}
                label={pick(modelIdentity.statusLabel, modelIdentity.statusLabelEn)}
                size="sm"
                pulse
              />
            </div>

            <p className="mt-1 font-mono text-[11px] text-foreground-500">
              {modelIdentity.codeName} · {pick(modelIdentity.algorithm, modelIdentity.algorithmEn)} ·{" "}
              {pick(modelIdentity.task, modelIdentity.taskEn)}
            </p>

            <p className="mt-2.5 max-w-3xl text-xs leading-relaxed text-foreground-600">
              {pick(modelIdentity.summary, modelIdentity.summaryEn)}
            </p>

            <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2">
              {meta.map((item) => (
                <span
                  key={item.label}
                  className="flex items-center gap-1.5 text-[11px] text-foreground-500"
                >
                  <span className="flex h-4 w-4 items-center justify-center">
                    <i className={`${item.icon} text-[13px]`}></i>
                  </span>
                  {item.label}
                  <span className="font-mono text-foreground-800">{item.value}</span>
                </span>
              ))}
            </div>
          </div>
        </div>

        <div className="grid shrink-0 grid-cols-2 gap-3 sm:grid-cols-4 xl:w-[440px]">
          {modelMetrics.map((metric) => (
            <div
              key={metric.key}
              className="rounded-md border border-background-200 bg-background-50 p-3"
            >
              <p className="font-mono text-[11px] text-foreground-500">{metric.label}</p>
              <p className="mt-1 font-mono text-lg font-semibold tracking-tight text-foreground-950">
                {metric.value}
              </p>
              <p className="mt-0.5 text-[10px] text-accent-400">
                {t(`model.hero.hints.${metric.key}`)}
              </p>
            </div>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-background-200/70 bg-background-50 px-5 py-3">
        <span className="flex items-center gap-1.5 text-[11px] text-foreground-500">
          <i className="ri-information-line text-[13px]"></i>
          {t("model.hero.footerNote")}
        </span>
        <Link
          to="/model"
          className="ml-auto flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md bg-primary-500 px-3.5 py-2 text-xs font-medium text-background-50 transition-colors hover:bg-primary-600"
        >
          <i className="ri-line-chart-line text-sm"></i>
          {t("model.hero.viewDashboard")}
        </Link>
        <Link
          to="/batch"
          className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border border-background-300 px-3 py-2 text-xs text-foreground-700 transition-colors hover:border-primary-400 hover:text-primary-400"
        >
          <i className="ri-stack-line text-sm"></i>
          {t("model.hero.batch")}
        </Link>
      </div>
    </section>
  );
}