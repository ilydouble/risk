import { useTranslation } from "react-i18next";
import type { BatchRun } from "@/entities/demo/model/types";

interface BatchRunPanelProps {
  run: BatchRun;
  stepIndex: number;
  done: boolean;
}

export default function BatchRunPanel({
  run,
  stepIndex,
  done,
}: BatchRunPanelProps) {
  const { t } = useTranslation();
  const total = run.steps.length;
  const progress = done ? 100 : Math.round((stepIndex / total) * 100);

  const meta: { label: string; value: string }[] = [
    { label: t("batch.run.batchId"), value: run.id },
    { label: t("batch.run.model"), value: run.modelVersion },
    {
      label: t("batch.run.scale"),
      value: t("batch.run.scaleUnit", { count: run.scanned }),
    },
    { label: t("batch.run.startedAt"), value: run.startedAt },
  ];

  return (
    <section className="animate-fade-up rounded-lg border border-background-200 bg-background-100 p-4 md:p-5">
      <header className="flex items-start gap-3">
        <span
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-md ${
            done
              ? "bg-primary-500/12 text-primary-400"
              : "bg-accent-500/12 text-accent-400"
          }`}
        >
          <i
            className={`${
              done ? "ri-checkbox-circle-line" : "ri-loader-4-line animate-spin"
            } text-[18px]`}
          ></i>
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-[15px] font-semibold text-foreground-950">
            {done ? t("batch.run.doneTitle") : t("batch.run.runningTitle")}
          </h2>
          <p className="mt-0.5 text-xs leading-relaxed text-foreground-500">
            {done
              ? t("batch.run.doneDesc", { count: run.scanned })
              : t("batch.run.runningDesc")}
          </p>
        </div>
        <span className="shrink-0 font-mono text-sm text-foreground-500">
          {progress}%
        </span>
      </header>

      <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-background-200">
        <div
          className="h-full rounded-full bg-primary-500 transition-[width] duration-300 ease-out"
          style={{ width: `${progress}%` }}
        ></div>
      </div>

      <ol className="mt-4 grid grid-cols-1 gap-2.5 sm:grid-cols-2 xl:grid-cols-5">
        {run.steps.map((step, index) => {
          const isDone = done || index < stepIndex;
          const isActive = !done && index === stepIndex;
          return (
            <li
              key={step.label}
              className={`flex items-start gap-2.5 rounded-md border p-3 transition-colors ${
                isDone
                  ? "border-primary-400/30 bg-primary-500/6"
                  : isActive
                    ? "border-accent-500/40 bg-accent-500/8"
                    : "border-background-200 bg-background-50"
              }`}
            >
              <span
                className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[11px] ${
                  isDone
                    ? "border-primary-400/40 bg-primary-500/14 text-primary-400"
                    : isActive
                      ? "border-accent-500/50 bg-accent-500/14 text-accent-400"
                      : "border-background-300 bg-background-50 text-foreground-500"
                }`}
              >
                {isDone ? (
                  <i className="ri-check-line"></i>
                ) : isActive ? (
                  <i className="ri-loader-4-line animate-spin"></i>
                ) : (
                  <i className="ri-more-line"></i>
                )}
              </span>
              <div className="min-w-0">
                <p
                  className={`text-[12px] font-medium ${
                    isDone || isActive
                      ? "text-foreground-900"
                      : "text-foreground-500"
                  }`}
                >
                  {step.label}
                </p>
                <p className="mt-0.5 text-[11px] leading-relaxed text-foreground-500">
                  {step.detail}
                </p>
              </div>
            </li>
          );
        })}
      </ol>

      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 border-t border-background-200/70 pt-4 sm:grid-cols-4">
        {meta.map((item) => (
          <div key={item.label}>
            <dt className="text-[10px] text-foreground-500">{item.label}</dt>
            <dd className="mt-0.5 truncate font-mono text-[12px] text-foreground-800">
              {item.value}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}