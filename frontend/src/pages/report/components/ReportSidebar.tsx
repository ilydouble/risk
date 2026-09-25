import { useTranslation } from "react-i18next";
import Card from "@/components/base/Card";
import { evidenceTypeMeta } from "@/pages/report/lib/report";
import { useLang } from "@/hooks/useLang";
import type { Evidence, EvidenceType, ReportDoc } from "@/types";

export interface SectionStatus {
  id: string;
  index: number;
  title: string;
  icon: string;
  revealed: number;
  count: number;
}

interface ReportSidebarProps {
  doc: ReportDoc;
  sectionStatus: SectionStatus[];
  revealed: number;
  total: number;
}

function scrollToSection(id: string) {
  const el = document.getElementById(`report-section-${id}`);
  if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
}

const EVIDENCE_ORDER: EvidenceType[] = [
  "graph",
  "feature",
  "snapshot",
  "fact",
  "benchmark",
  "flag",
  "timeline",
];

export default function ReportSidebar({
  doc,
  sectionStatus,
  revealed,
  total,
}: ReportSidebarProps) {
  const { t } = useTranslation();
  const { isEn } = useLang();

  const current =
    sectionStatus.find((section) => section.revealed < section.count) ??
    sectionStatus[sectionStatus.length - 1];

  const counts = EVIDENCE_ORDER.map((type) => ({
    type,
    count: doc.evidence.filter((item: Evidence) => item.type === type).length,
  })).filter((item) => item.count > 0);

  const maxCount = Math.max(...counts.map((item) => item.count), 1);

  return (
    <div className="space-y-4">
      <Card
        title={t("report.sidebar.progressTitle")}
        subtitle={t("report.sidebar.progressSub", { done: revealed, total })}
        icon="ri-loader-4-line"
        bodyClassName="p-4"
      >
        <div className="rounded-md border border-background-200 bg-background-50 p-3">
          <p className="text-[10px] text-foreground-500">{t("report.sidebar.current")}</p>
          <p className="mt-1 flex items-center gap-1.5 text-[12px] font-medium text-foreground-900">
            <i className={`${current?.icon} text-[14px] text-primary-400`}></i>
            {current?.title}
          </p>
        </div>
        <ul className="mt-3 space-y-2">
          {sectionStatus.map((section) => {
            const ratio =
              section.count === 0
                ? 100
                : Math.round((section.revealed / section.count) * 100);
            return (
              <li key={section.id}>
                <div className="flex items-center justify-between text-[10px] text-foreground-500">
                  <span className="truncate">{section.title}</span>
                  <span className="font-mono">{ratio}%</span>
                </div>
                <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-background-200">
                  <span
                    className="block h-full rounded-full bg-primary-500/70 transition-[width] duration-500"
                    style={{ width: `${ratio}%` }}
                  ></span>
                </div>
              </li>
            );
          })}
        </ul>
      </Card>

      <Card
        title={t("report.sidebar.tocTitle")}
        subtitle={t("report.sidebar.tocSub")}
        icon="ri-list-unordered"
        bodyClassName="p-2"
      >
        <ul>
          {sectionStatus.map((section) => {
            const ready = section.revealed > 0;
            return (
              <li key={section.id}>
                <button
                  type="button"
                  disabled={!ready}
                  onClick={() => scrollToSection(section.id)}
                  className={`flex w-full cursor-pointer items-center gap-2.5 rounded-md px-2.5 py-2 text-left transition-colors ${
                    ready
                      ? "text-foreground-700 hover:bg-background-200/60 hover:text-foreground-950"
                      : "cursor-not-allowed text-foreground-500"
                  }`}
                >
                  <span className="flex h-5 w-5 items-center justify-center rounded bg-background-200/80 font-mono text-[10px] text-foreground-600">
                    {String(section.index).padStart(2, "0")}
                  </span>
                  <span className="truncate text-[12px]">{section.title}</span>
                  <span className="ml-auto flex items-center gap-1 text-[10px] text-foreground-500">
                    {section.revealed >= section.count ? (
                      <i className="ri-check-line text-[12px] text-primary-400"></i>
                    ) : (
                      <i className="ri-more-line text-[12px]"></i>
                    )}
                    {section.revealed}/{section.count}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </Card>

      <Card
        title={t("report.sidebar.evidenceTitle")}
        subtitle={t("report.sidebar.evidenceSub", { count: doc.evidence.length })}
        icon="ri-links-line"
        bodyClassName="p-4"
      >
        <ul className="space-y-2.5">
          {counts.map((item) => {
            const meta = evidenceTypeMeta[item.type];
            return (
              <li key={item.type}>
                <div className="flex items-center gap-2">
                  <span
                    className={`flex h-5 w-5 items-center justify-center rounded ${meta.tone}`}
                  >
                    <i className={`${meta.icon} text-[11px]`}></i>
                  </span>
                  <span className="text-[11px] text-foreground-700">
                    {isEn ? meta.labelEn : meta.label}
                  </span>
                  <span className="ml-auto font-mono text-[11px] text-foreground-800">
                    {item.count}
                  </span>
                </div>
                <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-background-200">
                  <span
                    className="block h-full rounded-full bg-secondary-500/60"
                    style={{ width: `${(item.count / maxCount) * 100}%` }}
                  ></span>
                </div>
              </li>
            );
          })}
        </ul>
        <p className="mt-3 rounded-md border border-background-200/70 bg-background-50 p-2.5 text-[10px] leading-relaxed text-foreground-500">
          {t("report.sidebar.evidenceNote")}
        </p>
      </Card>
    </div>
  );
}