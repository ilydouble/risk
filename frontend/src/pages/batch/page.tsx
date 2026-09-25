import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import AppShell from "@/components/feature/AppShell";
import BatchUploadPanel from "@/pages/batch/components/BatchUploadPanel";
import BatchRunPanel from "@/pages/batch/components/BatchRunPanel";
import BatchSummary from "@/pages/batch/components/BatchSummary";
import BatchResultTable from "@/pages/batch/components/BatchResultTable";
import { useBatchRun } from "@/pages/batch/hooks/useBatchRun";
import {
  buildResultCsv,
  createSampleRoster,
  makeRosterFromText,
} from "@/pages/batch/lib/batch";
import { sampleRosterCsv, sampleRosterCsvEn } from "@/mocks/batchRoster";
import { useLang } from "@/hooks/useLang";
import type { BatchRoster } from "@/types";

export default function BatchPage() {
  const { t } = useTranslation();
  const { lang, isEn } = useLang();
  const [roster, setRoster] = useState<BatchRoster | null>(null);
  const [toast, setToast] = useState("");
  const batch = useBatchRun(roster, lang);

  const STEPS = [
    t("batch.steps.upload"),
    t("batch.steps.score"),
    t("batch.steps.export"),
  ];

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 2800);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const activeStep = useMemo(() => {
    if (batch.done) return 2;
    if (batch.started) return 1;
    if (roster) return 0;
    return 0;
  }, [batch.done, batch.started, roster]);

  const handleFile = (fileName: string, text: string) => {
    setRoster(makeRosterFromText(text, fileName));
    setToast(t("batch.toasts.parsed"));
  };

  const handleSample = () => {
    setRoster(createSampleRoster(isEn ? sampleRosterCsvEn : sampleRosterCsv));
    setToast(t("batch.toasts.sampleLoaded"));
  };

  const handleExport = () => {
    if (!batch.rows.length) return;
    const csv = buildResultCsv(batch.rows, lang);
    const blob = new Blob([`\uFEFF${csv}`], {
      type: "text/csv;charset=utf-8;",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = isEn
      ? `batch-evaluation-${batch.run?.id ?? "batch"}.csv`
      : `批量评估结果-${batch.run?.id ?? "batch"}.csv`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    setToast(t("batch.toasts.exported"));
  };

  const exporting = batch.done && batch.rows.length > 0;

  return (
    <AppShell
      title={t("batch.page.title")}
      subtitle={t("batch.page.subtitle")}
      actions={
        <>
          <Link
            to="/"
            className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border border-background-300 px-3 py-2 text-xs text-foreground-700 transition-colors hover:border-primary-400 hover:text-primary-400"
          >
            <i className="ri-arrow-left-line text-sm"></i>
            {t("batch.page.backToOverview")}
          </Link>
          <button
            type="button"
            disabled={!exporting}
            onClick={() => window.print()}
            className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border border-background-300 px-3 py-2 text-xs text-foreground-700 transition-colors hover:border-primary-400 hover:text-primary-400 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <i className="ri-printer-line text-sm"></i>
            {t("batch.page.exportPdf")}
          </button>
          <button
            type="button"
            disabled={!exporting}
            onClick={handleExport}
            className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md bg-primary-500 px-3.5 py-2 text-xs font-medium text-background-50 transition-colors hover:bg-primary-600 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <i className="ri-download-2-line text-sm"></i>
            {t("batch.page.exportResult")}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <ol className="animate-fade-up flex flex-wrap items-center gap-2">
          {STEPS.map((label, index) => {
            const done = index < activeStep || (index === 2 && batch.done);
            const active = index === activeStep && !batch.done;
            return (
              <li key={label} className="flex items-center gap-2">
                <span
                  className={`flex items-center gap-2 whitespace-nowrap rounded-full border px-3 py-1.5 text-[11px] transition-colors ${
                    done
                      ? "border-primary-400/40 bg-primary-500/10 text-primary-400"
                      : active
                        ? "border-accent-500/45 bg-accent-500/10 text-accent-400"
                        : "border-background-200 bg-background-100 text-foreground-500"
                  }`}
                >
                  <span className="flex h-4 w-4 items-center justify-center rounded-full font-mono text-[10px]">
                    {done ? (
                      <i className="ri-check-line text-[12px]"></i>
                    ) : (
                      index + 1
                    )}
                  </span>
                  {label}
                </span>
                {index < STEPS.length - 1 && (
                  <i className="ri-arrow-right-s-line text-sm text-foreground-500"></i>
                )}
              </li>
            );
          })}
        </ol>

        <BatchUploadPanel
          roster={roster}
          disabled={batch.started && !batch.done}
          onFile={handleFile}
          onSample={handleSample}
          onReset={() => setRoster(null)}
        />

        {roster && !batch.started && (
          <section className="animate-fade-up flex flex-col gap-3 rounded-lg border border-background-200 bg-background-100 p-4 md:flex-row md:items-center md:justify-between md:p-5">
            <div className="flex items-start gap-3">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary-500/12 text-primary-400">
                <i className="ri-play-circle-line text-[18px]"></i>
              </span>
              <div>
                <p className="text-[14px] font-semibold text-foreground-950">
                  {t("batch.ready.title", { count: roster.rawNames.length })}
                </p>
                <p className="mt-0.5 text-xs leading-relaxed text-foreground-500">
                  {t("batch.ready.desc")}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={batch.start}
              className="flex cursor-pointer items-center justify-center gap-1.5 whitespace-nowrap rounded-md bg-primary-500 px-4 py-2.5 text-xs font-medium text-background-50 transition-colors hover:bg-primary-600"
            >
              <i className="ri-flashlight-line text-sm"></i>
              {t("batch.ready.start")}
            </button>
          </section>
        )}

        {batch.started && !batch.done && batch.run && (
          <BatchRunPanel
            run={batch.run}
            stepIndex={batch.stepIndex}
            done={batch.done}
          />
        )}

        {batch.done && (
          <>
            <BatchSummary summary={batch.summary} />

            <BatchResultTable rows={batch.rows} />

            <section className="animate-fade-up flex flex-col gap-3 rounded-lg border border-background-200 bg-background-100 p-4 md:flex-row md:items-center md:justify-between md:p-5">
              <p className="text-xs leading-relaxed text-foreground-500">
                {t("batch.result.note", { count: batch.rows.length })}
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={batch.start}
                  className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border border-background-300 px-3 py-2 text-xs text-foreground-700 transition-colors hover:border-primary-400 hover:text-primary-400"
                >
                  <i className="ri-refresh-line text-sm"></i>
                  {t("batch.result.rescore")}
                </button>
                <button
                  type="button"
                  onClick={handleExport}
                  className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md bg-primary-500 px-3.5 py-2 text-xs font-medium text-background-50 transition-colors hover:bg-primary-600"
                >
                  <i className="ri-download-2-line text-sm"></i>
                  {t("batch.result.exportCsv")}
                </button>
              </div>
            </section>
          </>
        )}
      </div>

      {toast && (
        <div className="animate-fade-in fixed bottom-6 left-1/2 z-40 -translate-x-1/2 rounded-md border border-background-300 bg-background-100 px-4 py-2.5 text-xs text-foreground-900">
          <span className="flex items-center gap-2">
            <i className="ri-checkbox-circle-line text-base text-primary-400"></i>
            {toast}
          </span>
        </div>
      )}
    </AppShell>
  );
}