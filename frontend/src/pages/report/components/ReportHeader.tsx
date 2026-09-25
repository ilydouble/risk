import { useTranslation } from "react-i18next";
import RiskBadge from "@/entities/risk/ui/RiskBadge";
import { useLang } from "@/shared/lib/useLang";
import type { Company, ReportDoc } from "@/entities/demo/model/types";

interface ReportHeaderProps {
  company: Company;
  doc: ReportDoc;
  progress: number;
  revealed: number;
  total: number;
  playing: boolean;
  done: boolean;
  onRestart: () => void;
  onToggle: () => void;
  onComplete: () => void;
}

export default function ReportHeader({
  company,
  doc,
  progress,
  revealed,
  total,
  playing,
  done,
  onRestart,
  onToggle,
  onComplete,
}: ReportHeaderProps) {
  const { t } = useTranslation();
  const { isEn } = useLang();

  const meta = [
    { label: t("report.header.reportNo"), value: doc.id },
    { label: t("report.header.model"), value: doc.modelVersion },
    { label: t("report.header.generatedAt"), value: doc.generatedAt },
    { label: t("report.header.wordCount"), value: `${doc.wordCount}` },
  ];

  const statusText = done
    ? t("report.header.done", { total, ev: doc.evidence.length })
    : playing
      ? t("report.header.generating", { current: Math.min(revealed + 1, total), total })
      : t("report.header.paused", { done: revealed, total });

  return (
    <section className="animate-fade-up rounded-lg border border-background-200 bg-background-100">
      <div className="flex flex-col gap-3 border-b border-background-200/70 px-4 py-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-primary-500/12 text-primary-400">
            <i className="ri-building-2-line text-xl"></i>
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="font-heading text-[15px] font-semibold text-foreground-950">
                {isEn ? company.nameEn : company.nameCn}
              </h2>
              <RiskBadge level={company.riskLevel} size="sm" />
              <span className="rounded-full bg-background-200/80 px-2 py-0.5 font-mono text-[10px] text-foreground-600">
                {company.region} · {company.sector}
              </span>
            </div>
            <p className="mt-1 text-[11px] text-foreground-500">{company.nameEn}</p>
          </div>
        </div>

        <div className="flex flex-wrap gap-x-5 gap-y-1.5">
          {meta.map((item) => (
            <div key={item.label} className="min-w-[92px]">
              <p className="text-[10px] text-foreground-500">{item.label}</p>
              <p className="mt-0.5 font-mono text-[11px] text-foreground-800">
                {item.value}
              </p>
            </div>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-3 px-4 py-3 lg:flex-row lg:items-center">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onRestart}
            className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border border-background-300 px-3 py-2 text-xs text-foreground-700 transition-colors hover:border-primary-400 hover:text-primary-400"
          >
            <i className="ri-refresh-line text-sm"></i>
            {t("report.actionRestart")}
          </button>
          <button
            type="button"
            onClick={onToggle}
            disabled={done}
            className={`flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border px-3 py-2 text-xs transition-colors ${
              done
                ? "cursor-not-allowed border-background-200 text-foreground-500"
                : "border-background-300 text-foreground-700 hover:border-primary-400 hover:text-primary-400"
            }`}
          >
            <i className={`${playing ? "ri-pause-line" : "ri-play-line"} text-sm`}></i>
            {playing ? t("report.actionPause") : t("report.actionResume")}
          </button>
          <button
            type="button"
            onClick={onComplete}
            disabled={done}
            className={`flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border px-3 py-2 text-xs transition-colors ${
              done
                ? "cursor-not-allowed border-background-200 text-foreground-500"
                : "border-background-300 text-foreground-700 hover:border-primary-400 hover:text-primary-400"
            }`}
          >
            <i className="ri-skip-forward-line text-sm"></i>
            {t("report.actionSkip")}
          </button>
        </div>

        <div className="flex-1 lg:pl-4">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-[11px] text-foreground-500">
              {!done && playing && (
                <i className="ri-loader-4-line animate-spin text-[12px] text-primary-400"></i>
              )}
              {statusText}
            </span>
            <span className="font-mono text-[11px] font-medium text-primary-400">
              {progress}%
            </span>
          </div>
          <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-background-200">
            <span
              className="block h-full rounded-full bg-primary-500 transition-[width] duration-500"
              style={{ width: `${progress}%` }}
            ></span>
          </div>
        </div>
      </div>
    </section>
  );
}