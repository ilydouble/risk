import { useTranslation } from "react-i18next";
import Card from "@/components/base/Card";
import StatusPill from "@/components/base/StatusPill";
import Tooltip from "@/components/base/Tooltip";
import { RISK_HINT } from "@/constants/status";
import { driftMetrics, driftTrend } from "@/mocks/modelCard";
import { useLang } from "@/hooks/useLang";
import type { RiskLevel } from "@/types";

const PSI_MAX = 0.35;

const DRIFT_LABEL_KEY: Record<RiskLevel, string> = {
  low: "model.drift.stable",
  medium: "model.drift.watch",
  high: "model.drift.alert",
};

export default function DriftMonitorCard() {
  const { t } = useTranslation();
  const { pick } = useLang();
  return (
    <Card
      title={t("model.drift.title")}
      subtitle={t("model.drift.subtitle")}
      icon="ri-pulse-line"
      bodyClassName="p-4"
    >
      <div className="rounded-md border border-background-200 bg-background-50 p-3">
        <div className="flex items-center justify-between">
          <p className="text-[11px] text-foreground-500">{t("model.drift.chartLabel")}</p>
          <span className="font-mono text-[11px] text-foreground-500">
            {t("model.drift.threshold")}
          </span>
        </div>
        <div className="mt-3 flex items-end gap-2">
          {driftTrend.map((point) => {
            const height = Math.max(6, Math.round((point.psi / PSI_MAX) * 100));
            return (
              <div key={point.date} className="flex flex-1 flex-col items-center gap-1.5">
                <span className="font-mono text-[10px] text-foreground-600">
                  {point.psi.toFixed(2)}
                </span>
                <div className="flex h-20 w-full items-end overflow-hidden rounded-sm bg-background-200/70">
                  <span
                    className="block w-full rounded-sm bg-primary-500/70"
                    style={{ height: `${height}%` }}
                  ></span>
                </div>
                <span className="text-[10px] text-foreground-500">
                  {pick(point.date, point.dateEn)}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      <ul className="mt-3 space-y-2">
        {driftMetrics.map((metric) => (
          <li
            key={metric.key}
            className="flex items-center justify-between gap-3 rounded-md border border-background-200 bg-background-50 px-3 py-2"
          >
            <div className="min-w-0">
              <p className="truncate text-[12px] text-foreground-800">
                {pick(metric.label, metric.labelEn)}
              </p>
              <p className="mt-0.5 truncate text-[10px] text-foreground-500">
                {pick(metric.note, metric.noteEn)}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2.5">
              <Tooltip content={t("model.drift.psiTooltip", { hint: t(RISK_HINT[metric.status]) })}>
                <span className="font-mono text-[13px] font-semibold text-foreground-950">
                  {metric.psi.toFixed(2)}
                </span>
              </Tooltip>
              <StatusPill
                level={metric.status}
                label={t(DRIFT_LABEL_KEY[metric.status])}
                size="sm"
              />
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}