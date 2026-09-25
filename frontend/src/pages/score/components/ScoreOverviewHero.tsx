import { useTranslation } from "react-i18next";
import RiskBadge from "@/entities/risk/ui/RiskBadge";
import ScoreGauge from "@/pages/score/components/ScoreGauge";
import { chartPalette } from "@/shared/config/theme/palette";
import { useLang } from "@/shared/lib/useLang";
import { formatContribution } from "@/features/demo-scenarios/lib/score";
import type { Company, ScoreDetail } from "@/entities/demo/model/types";

interface ScoreOverviewHeroProps {
  company: Company;
  detail: ScoreDetail;
}

const RISK_GAUGE_COLOR: Record<Company["riskLevel"], string> = {
  low: chartPalette.riskLow,
  medium: chartPalette.riskMedium,
  high: chartPalette.riskHigh,
};

export default function ScoreOverviewHero({ company, detail }: ScoreOverviewHeroProps) {
  const { t } = useTranslation();
  const { isEn } = useLang();
  const gaugeColor = RISK_GAUGE_COLOR[company.riskLevel];

  const metrics = [
    {
      label: t("score.hero.pd"),
      value: `${detail.defaultProb.toFixed(1)}%`,
      sub: t("score.hero.pdSub", {
        base: detail.pdBase.toFixed(1),
        delta: formatContribution(detail.pdDelta),
      }),
      icon: "ri-alert-line",
      tone: "text-accent-400",
    },
    {
      label: t("score.hero.percentile"),
      value: `P${detail.riskPercentile}`,
      sub: t("score.hero.percentileSub", { pct: detail.riskPercentile }),
      icon: "ri-bar-chart-grouped-line",
      tone: "text-secondary-300",
    },
    {
      label: t("score.hero.confidence"),
      value: `${detail.confidence}%`,
      sub: t("score.hero.confidenceSub"),
      icon: "ri-focus-3-line",
      tone: "text-foreground-900",
    },
    {
      label: t("score.hero.limit"),
      value: company.creditLimit,
      sub: t("score.hero.limitSub"),
      icon: "ri-hand-coin-line",
      tone: "text-foreground-900",
    },
  ];

  const meta = [
    { label: t("score.hero.modelVersion"), value: detail.modelVersion },
    { label: t("score.hero.evaluatedAt"), value: detail.evaluatedAt },
    {
      label: t("score.hero.factors"),
      value: t("score.hero.factorsUnit", { count: detail.features.length }),
    },
    {
      label: t("score.hero.sample"),
      value: t("score.hero.sampleUnit", {
        count: detail.benchmarks[detail.benchmarks.length - 1].sampleSize,
      }),
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
          {meta.map((item) => (
            <div key={item.label} className="min-w-[96px]">
              <p className="text-[10px] text-foreground-500">{item.label}</p>
              <p className="mt-0.5 font-mono text-[11px] text-foreground-800">{item.value}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 p-5 lg:grid-cols-[300px_minmax(0,1fr)]">
        <div className="flex flex-col items-center justify-center rounded-lg border border-background-200/70 bg-background-50 px-4 py-5">
          <ScoreGauge score={detail.finalScore} color={gaugeColor} />
          <div className="mt-3 flex items-center gap-2">
            <span
              className="rounded-md px-2.5 py-1 font-mono text-lg font-semibold"
              style={{ color: gaugeColor, backgroundColor: `${gaugeColor}1f` }}
            >
              {detail.grade}
            </span>
            <span className="text-[11px] leading-snug text-foreground-500">
              {detail.gradeNote}
            </span>
          </div>
          <div className="mt-3 flex w-full items-center justify-center gap-4 border-t border-background-200/70 pt-3">
            <div className="text-center">
              <p className="font-mono text-sm font-semibold text-primary-400">
                {detail.positiveCount}
              </p>
              <p className="text-[10px] text-foreground-500">{t("score.hero.positive")}</p>
            </div>
            <div className="h-7 w-px bg-background-200"></div>
            <div className="text-center">
              <p className="font-mono text-sm font-semibold risk-text-high">
                {detail.negativeCount}
              </p>
              <p className="text-[10px] text-foreground-500">{t("score.hero.negative")}</p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {metrics.map((metric) => (
            <div
              key={metric.label}
              className="rounded-md border border-background-200 bg-background-50 p-4"
            >
              <div className="flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-md bg-background-200/70 text-foreground-500">
                  <i className={`${metric.icon} text-[14px]`}></i>
                </span>
                <span className="text-[11px] text-foreground-500">{metric.label}</span>
              </div>
              <p className={`mt-3 font-mono text-2xl font-semibold tracking-tight ${metric.tone}`}>
                {metric.value}
              </p>
              <p className="mt-1.5 text-[11px] text-foreground-500">{metric.sub}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}