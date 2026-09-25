import { useTranslation } from "react-i18next";
import StatCard from "@/components/base/StatCard";
import { useLang } from "@/hooks/useLang";
import type { BatchSummary as BatchSummaryData, RiskLevel } from "@/types";

interface BatchSummaryProps {
  summary: BatchSummaryData;
}

const RISK_BAR: Record<RiskLevel, string> = {
  low: "risk-bg-low",
  medium: "risk-bg-medium",
  high: "risk-bg-high",
};

const RISK_TEXT: Record<RiskLevel, string> = {
  low: "risk-text-low",
  medium: "risk-text-medium",
  high: "risk-text-high",
};

export default function BatchSummary({ summary }: BatchSummaryProps) {
  const { t } = useTranslation();
  const { pick } = useLang();
  const maxCount = Math.max(
    1,
    ...summary.riskDistribution.map((item) => item.count),
  );
  const unique = summary.matched - summary.duplicate;

  const cards = [
    {
      icon: "ri-list-check-2",
      label: t("batch.summary.total"),
      value: String(summary.total),
      unit: t("batch.summary.unitRecord"),
      tone: "secondary" as const,
    },
    {
      icon: "ri-link-m",
      label: t("batch.summary.matched"),
      value: String(summary.matched),
      unit: t("batch.summary.unitCompany"),
      tone: "primary" as const,
    },
    {
      icon: "ri-user-add-line",
      label: t("batch.summary.unmatched"),
      value: String(summary.unmatched),
      unit: t("batch.summary.unitCompany"),
      tone: "accent" as const,
    },
    {
      icon: "ri-bar-chart-box-line",
      label: t("batch.summary.avgScore"),
      value: String(summary.avgScore),
      unit: t("batch.summary.unitScore"),
      tone: "primary" as const,
    },
    {
      icon: "ri-alert-line",
      label: t("batch.summary.highRisk"),
      value: String(summary.highRisk),
      unit: t("batch.summary.unitCompany"),
      tone: "accent" as const,
    },
    {
      icon: "ri-global-line",
      label: t("batch.summary.countries"),
      value: String(summary.countries),
      unit: t("batch.summary.unitCountry"),
      tone: "secondary" as const,
    },
  ];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
        {cards.map((card, index) => (
          <StatCard
            key={card.label}
            icon={card.icon}
            label={card.label}
            value={card.value}
            unit={card.unit}
            tone={card.tone}
            delay={index * 50}
          />
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <section className="animate-fade-up rounded-lg border border-background-200 bg-background-100 p-4 lg:col-span-2">
          <header className="mb-3 flex items-center justify-between">
            <h3 className="text-[14px] font-semibold text-foreground-950">
              {t("batch.summary.distributionTitle")}
            </h3>
            <span className="text-[11px] text-foreground-500">
              {t("batch.summary.uniqueNote", { count: unique })}
            </span>
          </header>
          <div className="space-y-3">
            {summary.riskDistribution.map((item) => (
              <div key={item.level}>
                <div className="flex items-center justify-between text-[11px]">
                  <span className={`font-medium ${RISK_TEXT[item.level]}`}>
                    {pick(item.label, item.labelEn)}
                  </span>
                  <span className="font-mono text-foreground-700">
                    {t("batch.summary.companyUnit", { count: item.count })}
                    <span className="ml-1 text-foreground-500">
                      ({unique ? Math.round((item.count / unique) * 100) : 0}%)
                    </span>
                  </span>
                </div>
                <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-background-200">
                  <div
                    className={`h-full rounded-full ${RISK_BAR[item.level]} transition-[width] duration-500`}
                    style={{ width: `${(item.count / maxCount) * 100}%` }}
                  ></div>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="animate-fade-up rounded-lg border border-background-200 bg-background-100 p-4">
          <h3 className="text-[14px] font-semibold text-foreground-950">
            {t("batch.summary.notesTitle")}
          </h3>
          <ul className="mt-3 space-y-2.5 text-[11px] text-foreground-600">
            <li className="flex items-start gap-2">
              <i className="ri-checkbox-circle-line mt-0.5 text-[13px] text-primary-400"></i>
              {t("batch.summary.noteMatched", {
                matched: summary.matched,
                duplicate: summary.duplicate,
              })}
            </li>
            <li className="flex items-start gap-2">
              <i className="ri-error-warning-line mt-0.5 text-[13px] text-accent-400"></i>
              {t("batch.summary.noteReview", { review: summary.review })}
            </li>
            <li className="flex items-start gap-2">
              <i className="ri-question-line mt-0.5 text-[13px] text-foreground-500"></i>
              {t("batch.summary.noteUnmatched", { unmatched: summary.unmatched })}
            </li>
          </ul>
        </section>
      </div>
    </div>
  );
}