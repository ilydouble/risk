import { useTranslation } from "react-i18next";
import type { EvalMetric } from "@/types";

interface MetricCardsProps {
  metrics: EvalMetric[];
  onReproduce: (key: string) => void;
}

export default function MetricCards({ metrics, onReproduce }: MetricCardsProps) {
  const { t } = useTranslation();
  return (
    <section className="animate-fade-up">
      <header className="mb-3 flex items-end justify-between gap-4">
        <div>
          <h2 className="font-heading text-[15px] font-semibold text-foreground-950">
            {t("model.metrics.title")}
          </h2>
          <p className="mt-0.5 text-xs text-foreground-500">
            {t("model.metrics.subtitle")}
          </p>
        </div>
        <button
          type="button"
          onClick={() => onReproduce("all")}
          className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border border-background-300 px-3 py-2 text-xs text-foreground-700 transition-colors hover:border-primary-400 hover:text-primary-400"
        >
          <i className="ri-refresh-line text-sm"></i>
          {t("model.metrics.reproduceAll")}
        </button>
      </header>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric, index) => {
          const improved = metric.higherBetter
            ? metric.delta > 0
            : metric.delta < 0;
          const deltaIcon =
            metric.delta === 0
              ? "ri-subtract-line"
              : metric.delta > 0
                ? "ri-arrow-up-line"
                : "ri-arrow-down-line";
          const pass = metric.status === "pass";

          return (
            <div
              key={metric.key}
              className="animate-fade-up group relative overflow-hidden rounded-lg border border-background-200 bg-background-100 p-4 transition-colors duration-300 hover:border-background-300"
              style={{ animationDelay: `${index * 60}ms` }}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="font-mono text-[13px] font-semibold text-foreground-950">
                    {metric.label}
                  </p>
                  <p className="mt-0.5 truncate text-[11px] text-foreground-500">
                    {metric.fullLabel}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => onReproduce(metric.key)}
                  className="flex shrink-0 cursor-pointer items-center gap-1 whitespace-nowrap rounded-md border border-background-300 px-2 py-1 text-[10px] text-foreground-600 transition-colors hover:border-primary-400 hover:text-primary-400"
                >
                  <i className="ri-refresh-line text-[12px]"></i>
                  {t("model.metrics.reproduce")}
                </button>
              </div>

              <div className="mt-3 flex items-end justify-between gap-2">
                <p className="font-mono text-[28px] font-semibold leading-none tracking-tight text-foreground-950">
                  {metric.display}
                </p>
                <span
                  className={`flex items-center gap-0.5 rounded-full px-1.5 py-0.5 font-mono text-[10px] ${
                    improved
                      ? "bg-primary-500/12 text-primary-400"
                      : "bg-accent-500/12 text-accent-400"
                  }`}
                >
                  <i className={`${deltaIcon} text-[11px]`}></i>
                  {metric.deltaDisplay}
                </span>
              </div>

              <div className="mt-3 space-y-1.5 border-t border-background-200/70 pt-3 text-[11px]">
                <div className="flex items-center justify-between">
                  <span className="text-foreground-500">{t("model.metrics.target")}</span>
                  <span className="flex items-center gap-1.5">
                    <span className="font-mono text-foreground-700">
                      {metric.targetDisplay}
                    </span>
                    <span
                      className={`inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[10px] ${
                        pass
                          ? "bg-primary-500/12 text-primary-400"
                          : "bg-accent-500/12 text-accent-400"
                      }`}
                    >
                      <i
                        className={`${
                          pass ? "ri-check-line" : "ri-alert-line"
                        } text-[10px]`}
                      ></i>
                      {pass ? t("model.metrics.pass") : t("model.metrics.watch")}
                    </span>
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-foreground-500">{t("model.metrics.ci")}</span>
                  <span className="font-mono text-foreground-700">
                    {metric.ciRange}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-foreground-500">{t("model.metrics.prev")}</span>
                  <span className="font-mono text-foreground-700">
                    {metric.prev.toFixed(metric.display.split(".")[1].length)}
                  </span>
                </div>
              </div>

              <p className="mt-3 text-[11px] leading-relaxed text-foreground-500">
                {metric.hint}
              </p>

              <span className="pointer-events-none absolute -right-6 -top-6 h-20 w-20 rounded-full bg-primary-500/10 opacity-0 blur-2xl transition-opacity duration-300 group-hover:opacity-100"></span>
            </div>
          );
        })}
      </div>
    </section>
  );
}