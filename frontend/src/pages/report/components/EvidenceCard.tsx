import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { evidenceTypeMeta } from "@/pages/report/lib/report";
import { useLang } from "@/shared/lib/useLang";
import type { Evidence } from "@/entities/demo/model/types";

interface EvidenceCardProps {
  evidence: Evidence;
}

export default function EvidenceCard({ evidence }: EvidenceCardProps) {
  const { t } = useTranslation();
  const { isEn } = useLang();
  const meta = evidenceTypeMeta[evidence.type];

  return (
    <div className="rounded-md border border-background-200 bg-background-100 p-3">
      <div className="flex items-center gap-2">
        <span className="flex h-5 w-5 items-center justify-center rounded bg-background-200/80 font-mono text-[10px] font-semibold text-foreground-700">
          {evidence.number}
        </span>
        <span
          className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${meta.tone}`}
        >
          <i className={`${meta.icon} text-[11px]`}></i>
          {isEn ? meta.labelEn : meta.label}
        </span>
        {evidence.metric && (
          <span className="ml-auto font-mono text-[11px] font-medium text-foreground-800">
            {evidence.metric}
          </span>
        )}
      </div>

      <p className="mt-2 text-[12px] font-semibold leading-snug text-foreground-950">
        {evidence.title}
      </p>
      <p className="mt-1 text-[11px] leading-relaxed text-foreground-500">
        {evidence.snippet}
      </p>

      <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-background-200/70 pt-2 text-[10px] text-foreground-500">
        <span className="flex items-center gap-1">
          <i className="ri-link text-[11px]"></i>
          {evidence.source}
        </span>
        <span className="flex items-center gap-1">
          <i className="ri-checkbox-circle-line text-[11px] text-primary-400"></i>
          {t("report.evidence.confidence", { pct: evidence.confidence })}
        </span>
        <span className="flex items-center gap-1">
          <i className="ri-time-line text-[11px]"></i>
          {evidence.capturedAt}
        </span>
      </div>

      {evidence.refPath && (
        <Link
          to={evidence.refPath}
          className="mt-2.5 flex w-full cursor-pointer items-center justify-center gap-1.5 rounded-md border border-background-300 px-2.5 py-1.5 text-[11px] text-foreground-700 transition-colors hover:border-primary-400 hover:text-primary-400"
        >
          <i className={`${meta.icon} text-[12px]`}></i>
          {evidence.refLabel ?? t("report.evidence.viewSource")}
        </Link>
      )}
    </div>
  );
}