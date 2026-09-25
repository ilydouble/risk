import { useTranslation } from "react-i18next";
import Card from "@/shared/ui/Card";
import RiskBadge from "@/entities/risk/ui/RiskBadge";
import { useLang } from "@/shared/lib/useLang";
import type { RiskFlag } from "@/entities/demo/model/types";

interface RiskTagCloudProps {
  flags: RiskFlag[];
}

export default function RiskTagCloud({ flags }: RiskTagCloudProps) {
  const { t } = useTranslation();
  const { pick } = useLang();
  const alertCount = flags.filter((flag) => flag.level !== "low").length;

  return (
    <Card
      title={t("company.risk.title")}
      subtitle={t("company.risk.subtitle")}
      icon="ri-alert-line"
      bodyClassName="p-4"
      action={
        <span
          className={`rounded-full px-2.5 py-1 font-mono text-[11px] ${
            alertCount > 0
              ? "bg-accent-500/15 text-accent-400"
              : "bg-primary-500/12 text-primary-400"
          }`}
        >
          {alertCount > 0
            ? t("company.risk.pending", { count: alertCount })
            : t("company.risk.noRisk")}
        </span>
      }
    >
      {flags.length === 0 ? (
        <div className="flex flex-col items-center px-4 py-10 text-center">
          <span className="flex h-11 w-11 items-center justify-center rounded-full bg-primary-500/12 text-primary-400">
            <i className="ri-shield-check-line text-xl"></i>
          </span>
          <p className="mt-3 text-[13px] text-foreground-700">
            {t("company.risk.empty")}
          </p>
        </div>
      ) : (
        <ul className="space-y-3.5">
          {flags.map((flag) => (
            <li key={flag.id} className="flex gap-3">
              <span
                className={`mt-0.5 w-0.5 shrink-0 self-stretch rounded-full risk-bg-${flag.level}`}
              ></span>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[13px] font-medium text-foreground-950">
                    {pick(flag.label, flag.labelEn)}
                  </span>
                  <RiskBadge level={flag.level} size="sm" />
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-2">
                  <span className="rounded bg-background-200/80 px-1.5 py-0.5 text-[10px] text-foreground-600">
                    {pick(flag.category, flag.categoryEn)}
                  </span>
                  <span className="font-mono text-[10px] text-foreground-500">
                    {flag.source}
                  </span>
                </div>
                <p className="mt-1.5 text-xs leading-relaxed text-foreground-600">
                  {pick(flag.desc, flag.descEn)}
                </p>
                <p className="mt-1 font-mono text-[10px] text-foreground-500">
                  {t("company.risk.detectedAt", { date: flag.detectedAt })}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}