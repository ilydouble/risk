import { useTranslation } from "react-i18next";
import { useLang } from "@/shared/lib/useLang";
import { edgeTypeMeta, riskColor } from "@/features/demo-scenarios/lib/graph";
import type { GraphEdgeType, RiskLevel } from "@/entities/demo/model/types";

interface GraphLegendProps {
  edgeTypes: GraphEdgeType[];
}

const riskOrder: RiskLevel[] = ["low", "medium", "high"];

export default function GraphLegend({
  edgeTypes,
}: GraphLegendProps) {
  const { t } = useTranslation();
  const { isEn } = useLang();

  return (
    <section className="animate-fade-up rounded-lg border border-background-200 bg-background-100 p-4">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-foreground-500">
            {t("graph.legend.risk")}
          </p>
          <ul className="mt-2 space-y-1.5">
            {riskOrder.map((risk) => (
              <li key={risk} className="flex items-center gap-2">
                <span
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ backgroundColor: riskColor[risk] }}
                ></span>
                <span className="text-[11px] text-foreground-700">
                  {t(`risk.${risk}`)}
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-foreground-500">
            {t("graph.legend.edge")}
          </p>
          <ul className="mt-2 space-y-1.5">
            {edgeTypes.map((type) => {
              const meta = edgeTypeMeta[type];
              return (
                <li key={type} className="flex items-center gap-2">
                  <svg width="26" height="8" className="shrink-0">
                    <line
                      x1="0"
                      y1="4"
                      x2="26"
                      y2="4"
                      stroke={meta.color}
                      strokeWidth="1.6"
                      strokeDasharray={meta.dashed ? "4 4" : undefined}
                    />
                  </svg>
                  <span className="whitespace-nowrap text-[11px] text-foreground-700">
                    {isEn ? meta.labelEn : meta.label}
                  </span>
                </li>
              );
            })}
            <li className="flex items-center gap-2">
              <svg width="26" height="8" className="shrink-0">
                <line
                  x1="0"
                  y1="4"
                  x2="26"
                  y2="4"
                  stroke={riskColor.high}
                  strokeWidth="2"
                  strokeDasharray="6 6"
                />
              </svg>
              <span className="whitespace-nowrap text-[11px] text-accent-400">
                {t("graph.legend.riskPath")}
              </span>
            </li>
          </ul>
        </div>
      </div>
    </section>
  );
}
