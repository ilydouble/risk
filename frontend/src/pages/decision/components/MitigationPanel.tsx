import { useTranslation } from "react-i18next";
import Card from "@/shared/ui/Card";
import type { DecisionDoc, MitigationMeasure } from "@/entities/demo/model/types";

interface MitigationPanelProps {
  decision: DecisionDoc;
}

const REQUIREMENT_META: Record<
  MitigationMeasure["requirement"],
  { labelKey: string; className: string }
> = {
  required: {
    labelKey: "decision.mitigation.required",
    className: "risk-border-high risk-soft-high risk-text-high",
  },
  recommended: {
    labelKey: "decision.mitigation.recommended",
    className: "border-accent-500/40 bg-accent-500/12 text-accent-400",
  },
  standard: {
    labelKey: "decision.mitigation.standard",
    className: "border-primary-400/40 bg-primary-500/10 text-primary-400",
  },
};

export default function MitigationPanel({ decision }: MitigationPanelProps) {
  const { t } = useTranslation();

  return (
    <Card
      title={t("decision.mitigation.title")}
      subtitle={t("decision.mitigation.subtitle")}
      icon="ri-shield-star-line"
      bodyClassName="p-4"
      action={
        <span className="whitespace-nowrap rounded-full bg-background-200/80 px-2.5 py-1 font-mono text-[10px] text-foreground-600">
          {t("decision.mitigation.count", { count: decision.mitigations.length })}
        </span>
      }
    >
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {decision.mitigations.map((measure) => {
          const req = REQUIREMENT_META[measure.requirement];
          return (
            <div
              key={measure.id}
              className="rounded-md border border-background-200 bg-background-50 p-4"
            >
              <div className="flex items-center justify-between">
                <span className="flex h-9 w-9 items-center justify-center rounded-md bg-primary-500/12 text-primary-400">
                  <i className={`${measure.icon} text-[17px]`}></i>
                </span>
                <span
                  className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${req.className}`}
                >
                  {t(req.labelKey)}
                </span>
              </div>
              <p className="mt-3 text-[12px] font-semibold text-foreground-950">
                {measure.title}
              </p>
              <p className="mt-1.5 text-[11px] leading-relaxed text-foreground-500">
                {measure.detail}
              </p>
            </div>
          );
        })}
      </div>
    </Card>
  );
}