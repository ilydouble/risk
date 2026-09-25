import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import Card from "@/shared/ui/Card";
import { formatContribution } from "@/features/demo-scenarios/lib/score";
import { chartPalette } from "@/shared/config/theme/palette";
import type { ShapFeature } from "@/entities/demo/model/types";

interface ShapFeatureTableProps {
  features: ShapFeature[];
}

type SortMode = "impact" | "positive" | "negative";

export default function ShapFeatureTable({ features }: ShapFeatureTableProps) {
  const { t } = useTranslation();
  const [sortMode, setSortMode] = useState<SortMode>("impact");

  const sortOptions: { value: SortMode; label: string }[] = [
    { value: "impact", label: t("score.featureTable.sortImpact") },
    { value: "positive", label: t("score.featureTable.sortPositive") },
    { value: "negative", label: t("score.featureTable.sortNegative") },
  ];

  const sorted = useMemo(() => {
    const list = [...features];
    if (sortMode === "positive") {
      return list.sort((a, b) => b.contribution - a.contribution);
    }
    if (sortMode === "negative") {
      return list.sort((a, b) => a.contribution - b.contribution);
    }
    return list.sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution));
  }, [features, sortMode]);

  const maxAbs = useMemo(
    () => Math.max(...features.map((item) => Math.abs(item.contribution)), 1),
    [features],
  );

  return (
    <Card
      title={t("score.featureTable.title")}
      subtitle={t("score.featureTable.subtitle")}
      icon="ri-list-check-2"
      bodyClassName="p-0"
      action={
        <div className="flex items-center gap-1 rounded-full border border-background-200 bg-background-50 p-1">
          {sortOptions.map((option) => {
            const active = option.value === sortMode;
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => setSortMode(option.value)}
                className={`cursor-pointer whitespace-nowrap rounded-full px-3 py-1 text-[11px] transition-colors ${
                  active
                    ? "bg-primary-500 font-medium text-background-50"
                    : "text-foreground-600 hover:text-foreground-900"
                }`}
              >
                {option.label}
              </button>
            );
          })}
        </div>
      }
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] border-collapse">
          <thead>
            <tr className="border-b border-background-200/70 text-left">
              <th className="px-4 py-2.5 text-[11px] font-medium text-foreground-500">{t("score.featureTable.colFactor")}</th>
              <th className="px-4 py-2.5 text-[11px] font-medium text-foreground-500">{t("score.featureTable.colValue")}</th>
              <th className="px-4 py-2.5 text-[11px] font-medium text-foreground-500">{t("score.featureTable.colContribution")}</th>
              <th className="px-4 py-2.5 text-[11px] font-medium text-foreground-500">{t("score.featureTable.colExplain")}</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((feature) => {
              const isPositive = feature.contribution >= 0;
              const color = isPositive ? chartPalette.primary : chartPalette.riskHigh;
              const width = (Math.abs(feature.contribution) / maxAbs) * 100;

              return (
                <tr
                  key={feature.id}
                  className="border-b border-background-200/50 transition-colors last:border-0 hover:bg-background-50"
                >
                  <td className="px-4 py-3 align-top">
                    <p className="text-[12px] font-medium text-foreground-900">{feature.label}</p>
                    <span className="mt-1 inline-block rounded-full bg-secondary-500/12 px-2 py-0.5 text-[10px] text-secondary-300">
                      {feature.category}
                    </span>
                  </td>
                  <td className="px-4 py-3 align-top">
                    <span className="font-mono text-[11px] text-foreground-600">{feature.value}</span>
                  </td>
                  <td className="px-4 py-3 align-top">
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-background-200">
                        <span
                          className="block h-full rounded-full"
                          style={{ width: `${width}%`, backgroundColor: color }}
                        ></span>
                      </div>
                      <span
                        className="font-mono text-[11px] font-medium"
                        style={{ color }}
                      >
                        {formatContribution(feature.contribution)}
                      </span>
                    </div>
                  </td>
                  <td className="max-w-[320px] px-4 py-3 align-top">
                    <p className="text-[11px] leading-relaxed text-foreground-500">{feature.desc}</p>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}