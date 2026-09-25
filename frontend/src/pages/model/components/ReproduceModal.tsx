import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import type { ReproduceRun } from "@/types";

interface ReproduceModalProps {
  run: ReproduceRun | null;
  stepIndex: number;
  done: boolean;
  onClose: () => void;
  onRestart: () => void;
}

export default function ReproduceModal({
  run,
  stepIndex,
  done,
  onClose,
  onRestart,
}: ReproduceModalProps) {
  const { t } = useTranslation();

  useEffect(() => {
    if (!run) return undefined;
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [run, onClose]);

  if (!run) return null;

  const total = run.steps.length;
  const progress = done ? 100 : Math.round((stepIndex / total) * 100);

  const meta: { label: string; value: string }[] = [
    { label: t("model.reproduce.runId"), value: run.runId },
    { label: t("model.reproduce.snapshot"), value: run.snapshot },
    { label: t("model.reproduce.seed"), value: run.seed },
    { label: t("model.reproduce.sampleSize"), value: run.sampleSize.toLocaleString("en-US") },
    { label: t("model.reproduce.engine"), value: run.engine },
    { label: t("model.reproduce.startedAt"), value: run.startedAt },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4 py-8">
      <button
        type="button"
        aria-label={t("model.reproduce.closeAria")}
        onClick={onClose}
        className="absolute inset-0 cursor-default bg-background-950/70 backdrop-blur-sm"
      ></button>

      <div className="animate-fade-up relative flex max-h-full w-full max-w-xl flex-col overflow-hidden rounded-lg border border-background-300 bg-background-100">
        <header className="flex items-start gap-3 border-b border-background-200/70 px-5 py-4">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary-500/12 text-primary-400">
            <i
              className={`${
                done ? "ri-checkbox-circle-line" : "ri-refresh-line animate-spin"
              } text-[18px]`}
            ></i>
          </span>
          <div className="min-w-0 flex-1">
            <h3 className="text-[15px] font-semibold text-foreground-950">
              {run.title}
            </h3>
            <p className="mt-0.5 text-xs leading-relaxed text-foreground-500">
              {run.subtitle}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("model.reproduce.close")}
            className="flex h-7 w-7 shrink-0 cursor-pointer items-center justify-center rounded-md text-foreground-500 transition-colors hover:bg-background-200 hover:text-foreground-900"
          >
            <i className="ri-close-line text-lg"></i>
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          <div className="flex items-center justify-between text-[11px] text-foreground-500">
            <span className="flex items-center gap-1.5">
              <i
                className={`${
                  done ? "ri-checkbox-circle-fill text-primary-400" : "ri-loader-4-line"
                } text-[13px]`}
              ></i>
              {done ? t("model.reproduce.complete") : t("model.reproduce.running")}
            </span>
            <span className="font-mono">{progress}%</span>
          </div>
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-background-200">
            <div
              className="h-full rounded-full bg-primary-500 transition-[width] duration-300 ease-out"
              style={{ width: `${progress}%` }}
            ></div>
          </div>

          <ol className="mt-4 space-y-2.5">
            {run.steps.map((step, index) => {
              const isDone = done || index < stepIndex;
              const isActive = !done && index === stepIndex;
              return (
                <li key={step.label} className="flex items-start gap-3">
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
                  <div className="min-w-0 flex-1">
                    <p
                      className={`text-[13px] font-medium ${
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
                  {isDone && (
                    <span className="shrink-0 font-mono text-[10px] text-foreground-500">
                      {(step.durationMs / 1000).toFixed(2)}s
                    </span>
                  )}
                </li>
              );
            })}
          </ol>

          {done && (
            <div className="animate-fade-in mt-4 rounded-md border border-primary-400/30 bg-primary-500/8 p-4">
              <div className="flex items-center justify-between">
                <p className="text-[11px] text-foreground-500">
                  {run.focusLabel}
                </p>
                <span className="inline-flex items-center gap-1 rounded-full border border-primary-400/40 bg-primary-500/12 px-2 py-0.5 text-[10px] font-medium text-primary-400">
                  <i className="ri-shield-check-line text-[12px]"></i>
                  {t("model.reproduce.matchBaseline")}
                </span>
              </div>
              <p className="mt-1 font-mono text-xl font-semibold text-foreground-950">
                {run.focusValue}
              </p>
              <p className="mt-1 text-[11px] leading-relaxed text-foreground-500">
                {run.focusNote}
              </p>
            </div>
          )}

          <div className="mt-4 rounded-md border border-background-200/70 bg-background-50 p-3">
            <p className="flex items-center gap-1.5 text-[11px] font-medium text-foreground-700">
              <i className="ri-terminal-box-line text-[13px] text-foreground-500"></i>
              {t("model.reproduce.logs")}
            </p>
            <div className="mt-2 space-y-1 font-mono text-[10px] leading-relaxed text-foreground-500">
              {run.logs.map((line) => (
                <p key={line} className="truncate">
                  {line}
                </p>
              ))}
            </div>
          </div>

          <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3">
            {meta.map((item) => (
              <div key={item.label}>
                <dt className="text-[10px] text-foreground-500">{item.label}</dt>
                <dd className="mt-0.5 truncate font-mono text-[11px] text-foreground-800">
                  {item.value}
                </dd>
              </div>
            ))}
          </dl>
        </div>

        <footer className="flex items-center justify-between gap-3 border-t border-background-200/70 px-5 py-3">
          <span className="flex items-center gap-1.5 text-[11px] text-foreground-500">
            <i className="ri-timer-line text-[13px]"></i>
            {t("model.reproduce.duration", { value: run.duration })}
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border border-background-300 px-3 py-1.5 text-xs text-foreground-700 transition-colors hover:border-background-400 hover:text-foreground-950"
            >
              {t("model.reproduce.close")}
            </button>
            <button
              type="button"
              onClick={onRestart}
              className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md bg-primary-500 px-3.5 py-1.5 text-xs font-medium text-background-50 transition-colors hover:bg-primary-600"
            >
              <i className="ri-refresh-line text-sm"></i>
              {t("model.reproduce.restart")}
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}