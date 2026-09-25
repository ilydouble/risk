import { useTranslation } from "react-i18next";
import Card from "@/components/base/Card";
import type { AblationRow } from "@/types";

interface GlobalImportanceCardProps {
  rows: AblationRow[];
  baselineAuc: number;
}

export default function GlobalImportanceCard({
  rows,
  baselineAuc,
}: GlobalImportanceCardProps) {
  const { t } = useTranslation();
  return (
    <Card
      title={t("model.importance.title")}
      subtitle={t("model.importance.subtitle", { value: baselineAuc.toFixed(3) })}
      icon="ri-bar-chart-horizontal-line"
      action={
        <span className="whitespace-nowrap rounded-full bg-background-200/70 px-2 py-0.5 font-mono text-[10px] text-foreground-500">
          {t("model.importance.badge")}
        </span>
      }
      bodyClassName="p-4"
    >
      <ul className="space-y-3.5">
        {rows.map((row, index) => (
          <li key={row.id} className="group">
            <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
              <div className="flex items-center gap-2">
                <span className="w-5 shrink-0 font-mono text-[11px] text-foreground-400">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span className="text-[13px] font-medium text-foreground-900">
                  {row.label}
                </span>
                <span className="font-mono text-[10px] text-foreground-500">
                  {t("model.importance.dimUnit", { count: row.featureCount })}
                </span>
              </div>
              <div className="flex items-center gap-3 font-mono text-[11px]">
                <span className="text-foreground-500">
                  {t("model.importance.afterAuc")} {row.auc.toFixed(3)}
                </span>
                <span className="flex items-center gap-1 text-primary-400">
                  <i className="ri-arrow-down-line text-[12px]"></i>
                  {row.aucDrop.toFixed(3)}
                </span>
              </div>
            </div>

            <div className="mt-1.5 flex items-center gap-2 pl-7">
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-background-200">
                <span
                  className={`block h-full rounded-full ${
                    index === 0 ? "bg-accent-500" : "bg-primary-500/70"
                  }`}
                  style={{ width: `${row.importance}%` }}
                ></span>
              </div>
              <span className="w-10 shrink-0 text-right font-mono text-[11px] text-foreground-700">
                {row.importance}%
              </span>
            </div>

            <p className="mt-1 pl-7 text-[11px] leading-relaxed text-foreground-500">
              {row.note}
            </p>
          </li>
        ))}
      </ul>
    </Card>
  );
}