import { useTranslation } from "react-i18next";
import Card from "@/components/base/Card";
import RiskBadge from "@/components/base/RiskBadge";
import { useLang } from "@/hooks/useLang";
import type { RelatedParty } from "@/types";

interface RelatedPartiesPanelProps {
  parties: RelatedParty[];
}

export default function RelatedPartiesPanel({
  parties,
}: RelatedPartiesPanelProps) {
  const { t } = useTranslation();
  const { pick } = useLang();
  const riskyCount = parties.filter((party) => party.riskLevel === "high").length;

  return (
    <Card
      title={t("company.parties.title")}
      subtitle={t("company.parties.subtitle")}
      icon="ri-share-forward-line"
      bodyClassName="p-4"
      action={
        <span className="whitespace-nowrap rounded-full bg-background-200/80 px-2.5 py-1 font-mono text-[11px] text-foreground-600">
          {t("company.parties.count", { count: parties.length })}
        </span>
      }
    >
      <ul className="space-y-2.5">
        {parties.map((party) => (
          <li
            key={party.id}
            className={`rounded-md border p-3 ${
              party.riskLevel === "high"
                ? "risk-soft-high risk-border-high"
                : "border-background-200/70 bg-background-50"
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-[13px] font-medium text-foreground-950">
                  {pick(party.name, party.nameEn)}
                </p>
                <p className="mt-0.5 text-[11px] text-foreground-500">
                  {pick(party.relation, party.relationEn)}
                </p>
              </div>
              <RiskBadge level={party.riskLevel} size="sm" />
            </div>
            <p className="mt-2 font-mono text-[11px] text-foreground-600">
              {pick(party.exposure, party.exposureEn)}
            </p>
          </li>
        ))}
      </ul>

      {riskyCount > 0 && (
        <div className="mt-3 flex items-start gap-2 rounded-md border border-background-200/70 bg-background-50 p-3">
          <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center text-accent-400">
            <i className="ri-lightbulb-line text-[14px]"></i>
          </span>
          <p className="text-[11px] leading-relaxed text-foreground-600">
            {t("company.parties.tip", { count: riskyCount })}
          </p>
        </div>
      )}
    </Card>
  );
}