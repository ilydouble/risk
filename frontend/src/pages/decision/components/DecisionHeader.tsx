import { useTranslation } from "react-i18next";
import RiskBadge from "@/entities/risk/ui/RiskBadge";
import { decisionOutcomeMeta } from "@/pages/decision/lib/decision";
import { useLang } from "@/shared/lib/useLang";
import type { Company, DecisionDoc } from "@/entities/demo/model/types";

interface DecisionHeaderProps {
  company: Company;
  decision: DecisionDoc;
}

const OUTCOME_CLASS: Record<
  DecisionDoc["outcome"],
  { wrap: string; icon: string; badge: string }
> = {
  approve: {
    wrap: "border-primary-400/40 bg-primary-500/10",
    icon: "bg-primary-500/15 text-primary-400",
    badge: "border-primary-400/40 bg-primary-500/15 text-primary-400",
  },
  conditional: {
    wrap: "border-accent-500/40 bg-accent-500/10",
    icon: "bg-accent-500/20 text-accent-400",
    badge: "border-accent-500/40 bg-accent-500/15 text-accent-400",
  },
  reject: {
    wrap: "risk-border-high risk-soft-high",
    icon: "risk-soft-high risk-text-high",
    badge: "risk-border-high risk-soft-high risk-text-high",
  },
};

export default function DecisionHeader({ company, decision }: DecisionHeaderProps) {
  const { t } = useTranslation();
  const { isEn } = useLang();
  const meta = decisionOutcomeMeta[decision.outcome];
  const style = OUTCOME_CLASS[decision.outcome];

  const infoMeta = [
    { label: t("decision.header.decisionNo"), value: decision.id },
    { label: t("decision.header.model"), value: decision.modelVersion },
    { label: t("decision.header.decidedAt"), value: decision.decidedAt },
    { label: t("decision.header.validUntil"), value: decision.validUntil },
  ];

  const figures = [
    {
      label: decision.limitLabel,
      value: decision.creditLimit,
      icon: "ri-hand-coin-line",
      tone: "text-foreground-950",
    },
    {
      label: decision.terms[0].label,
      value: decision.terms[0].value,
      icon: "ri-calendar-schedule-line",
      tone: "text-foreground-900",
    },
    {
      label: decision.terms[2].label,
      value: decision.terms[2].value,
      icon: "ri-refund-2-line",
      tone: "text-foreground-900",
    },
    {
      label: decision.terms[5].label,
      value: decision.terms[5].value,
      icon: "ri-radar-line",
      tone: "text-foreground-900",
    },
  ];

  return (
    <section className="animate-fade-up overflow-hidden rounded-lg border border-background-200 bg-background-100">
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
          {infoMeta.map((item) => (
            <div key={item.label} className="min-w-[96px]">
              <p className="text-[10px] text-foreground-500">{item.label}</p>
              <p className="mt-0.5 font-mono text-[11px] text-foreground-800">
                {item.value}
              </p>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 p-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <div className={`flex items-start gap-4 rounded-lg border p-4 ${style.wrap}`}>
          <span
            className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-lg ${style.icon}`}
          >
            <i className={`${meta.icon} text-2xl`}></i>
          </span>
          <div className="min-w-0">
            <span
              className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${style.badge}`}
            >
              {decision.outcomeLabel}
            </span>
            <p className="mt-2 text-[12px] leading-relaxed text-foreground-700">
              {decision.outcomeNote}
            </p>
            <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-foreground-500">
              <span className="flex items-center gap-1">
                <i className="ri-user-star-line text-[12px]"></i>
                {t("decision.header.approver", { name: decision.approver })}
              </span>
              <span className="flex items-center gap-1">
                <i className="ri-shield-check-line text-[12px]"></i>
                {t("decision.header.hitRules", {
                  hit: decision.hitCount,
                  total: decision.rules.length,
                })}
              </span>
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {figures.map((figure) => (
            <div
              key={figure.label}
              className="rounded-md border border-background-200 bg-background-50 p-3.5"
            >
              <div className="flex items-center gap-1.5">
                <span className="flex h-5 w-5 items-center justify-center text-foreground-500">
                  <i className={`${figure.icon} text-[13px]`}></i>
                </span>
                <span className="text-[11px] text-foreground-500">
                  {figure.label}
                </span>
              </div>
              <p
                className={`mt-2 font-mono text-lg font-semibold tracking-tight ${figure.tone}`}
              >
                {figure.value}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}