import { useTranslation } from "react-i18next";
import Card from "@/shared/ui/Card";
import { chartPalette } from "@/shared/config/theme/palette";
import type { DecisionDoc } from "@/entities/demo/model/types";

interface CreditLimitPanelProps {
  decision: DecisionDoc;
}

export default function CreditLimitPanel({ decision }: CreditLimitPanelProps) {
  const { t } = useTranslation();
  const maxAbs = Math.max(
    ...decision.factors.map((item) => Math.abs(item.amount)),
    1,
  );

  return (
    <Card
      title={t("decision.limits.title")}
      subtitle={t("decision.limits.subtitle", { label: decision.limitLabel })}
      icon="ri-calculator-line"
      bodyClassName="p-4"
      action={
        <span className="whitespace-nowrap rounded-full bg-background-200/80 px-2.5 py-1 font-mono text-[10px] text-foreground-600">
          {t("decision.limits.baseRatio", { pct: Math.round(decision.baseRatio * 100) })}
        </span>
      }
    >
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {decision.bands.map((band) => (
          <div
            key={band.key}
            className={`rounded-md border p-4 ${
              band.emphasis
                ? "border-primary-400/50 bg-primary-500/10"
                : "border-background-200 bg-background-50"
            }`}
          >
            <div className="flex items-center justify-between">
              <span
                className={`text-[11px] ${band.emphasis ? "font-medium text-primary-300" : "text-foreground-500"}`}
              >
                {band.label}
              </span>
              {band.emphasis && (
                <span className="flex h-4 w-4 items-center justify-center text-primary-400">
                  <i className="ri-focus-3-line text-[13px]"></i>
                </span>
              )}
            </div>
            <p
              className={`mt-2 font-mono text-lg font-semibold tracking-tight ${
                band.emphasis ? "text-primary-400" : "text-foreground-900"
              }`}
            >
              {band.display}
            </p>
            <p className="mt-1.5 text-[10px] leading-relaxed text-foreground-500">
              {band.note}
            </p>
          </div>
        ))}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-2 rounded-md border border-background-200/70 bg-background-50 px-4 py-3">
        <span className="text-[11px] text-foreground-500">{t("decision.limits.calc")}</span>
        <span className="font-mono text-[12px] text-foreground-900">
          {decision.baseLimit}
        </span>
        <span className="text-foreground-400">{t("decision.limits.base")}</span>
        <i className="ri-add-line text-sm text-foreground-400"></i>
        <span
          className="font-mono text-[12px] font-medium"
          style={{
            color: decision.adjustmentPositive
              ? chartPalette.primary
              : chartPalette.riskHigh,
          }}
        >
          {decision.adjustmentDisplay}
        </span>
        <span className="text-foreground-400">{t("decision.limits.riskAdj")}</span>
        <i className="ri-arrow-right-line text-sm text-foreground-400"></i>
        <span className="font-mono text-[13px] font-semibold text-primary-400">
          {decision.creditLimit}
        </span>
        <span className="ml-auto font-mono text-[10px] text-foreground-500">
          {decision.limitLabel}
        </span>
      </div>

      <div className="mt-4">
        <p className="mb-2.5 flex items-center gap-1.5 text-[11px] font-medium text-foreground-700">
          <i className="ri-equalizer-2-line text-[13px] text-foreground-500"></i>
          {t("decision.limits.detailTitle")}
        </p>
        <ul className="space-y-3">
          {decision.factors.map((factor) => {
            const width = (Math.abs(factor.amount) / maxAbs) * 50;
            const color = factor.positive
              ? chartPalette.primary
              : chartPalette.riskHigh;
            return (
              <li key={factor.id}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[12px] font-medium text-foreground-900">
                      {factor.label}
                    </p>
                    <p className="mt-0.5 text-[10px] leading-relaxed text-foreground-500">
                      {factor.detail}
                    </p>
                  </div>
                  <span
                    className="shrink-0 font-mono text-[12px] font-medium"
                    style={{ color }}
                  >
                    {factor.positive ? "+" : "−"}
                    {factor.display}
                  </span>
                </div>
                <div className="relative mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-background-200">
                  <span className="absolute left-1/2 top-0 h-full w-px bg-background-400/60"></span>
                  <span
                    className="absolute top-0 h-full rounded-full"
                    style={{
                      left: factor.positive ? "50%" : `${50 - width}%`,
                      width: `${Math.max(width, 1.5)}%`,
                      backgroundColor: color,
                    }}
                  ></span>
                </div>
              </li>
            );
          })}
        </ul>
      </div>

      <p className="mt-4 rounded-md border border-background-200/70 bg-background-50 p-2.5 text-[10px] leading-relaxed text-foreground-500">
        {t("decision.limits.note", { pct: Math.round(decision.baseRatio * 100) })}
      </p>
    </Card>
  );
}