import { useTranslation } from "react-i18next";
import Card from "@/shared/ui/Card";
import type { DecisionDoc, DecisionTerm } from "@/entities/demo/model/types";

interface TermsPanelProps {
  decision: DecisionDoc;
}

const TONE_MAP: Record<DecisionTerm["tone"], string> = {
  primary: "bg-primary-500/12 text-primary-400",
  accent: "bg-accent-500/15 text-accent-400",
  secondary: "bg-secondary-500/14 text-secondary-300",
};

export default function TermsPanel({ decision }: TermsPanelProps) {
  const { t } = useTranslation();
  return (
    <Card
      title={t("decision.terms.title")}
      subtitle={t("decision.terms.subtitle")}
      icon="ri-exchange-dollar-line"
      bodyClassName="p-4"
    >
      <ul className="space-y-2.5">
        {decision.terms.map((term) => (
          <li
            key={term.key}
            className="flex items-start gap-3 rounded-md border border-background-200/70 bg-background-50 p-3"
          >
            <span
              className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md ${TONE_MAP[term.tone]}`}
            >
              <i className={`${term.icon} text-[15px]`}></i>
            </span>
            <div className="min-w-0">
              <p className="text-[10px] text-foreground-500">{term.label}</p>
              <p className="mt-0.5 font-mono text-[12px] font-medium text-foreground-950">
                {term.value}
              </p>
              <p className="mt-1 text-[10px] leading-relaxed text-foreground-500">
                {term.note}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}