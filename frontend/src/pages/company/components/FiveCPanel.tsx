import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { useTranslation } from "react-i18next";
import Card from "@/shared/ui/Card";
import { useLang } from "@/shared/lib/useLang";
import { chartPalette } from "@/shared/config/theme/palette";
import type { FiveCDimension } from "@/entities/demo/model/types";

interface FiveCPanelProps {
  dimensions: FiveCDimension[];
}

interface TooltipPayloadItem {
  payload?: FiveCDimension;
}

interface TooltipProps {
  payload?: TooltipPayloadItem[];
}

function DimensionTooltip({ payload }: TooltipProps) {
  const { pick } = useLang();
  const item = payload?.[0]?.payload;
  if (!item) {
    return null;
  }
  return (
    <div className="max-w-[220px] rounded-md border border-background-300 bg-background-100 px-3 py-2">
      <p className="text-xs text-foreground-500">
        {pick(item.label, item.en)}
      </p>
      <p className="mt-1 font-mono text-sm font-semibold text-foreground-950">
        {item.score} / 100
      </p>
      <p className="mt-1 text-[11px] leading-relaxed text-foreground-600">
        {pick(item.note, item.noteEn)}
      </p>
    </div>
  );
}

function barTone(score: number): string {
  if (score >= 70) return "bg-primary-500";
  if (score >= 50) return "bg-accent-500";
  return "bg-foreground-500";
}

export default function FiveCPanel({ dimensions }: FiveCPanelProps) {
  const { t } = useTranslation();
  const { isEn, pick } = useLang();

  const weighted =
    dimensions.reduce((sum, item) => sum + item.score * item.weight, 0) / 100;

  const chartData = dimensions.map((item) => ({
    dimension: pick(item.label, item.en),
    score: item.score,
    ...item,
  }));

  return (
    <Card
      title={t("company.fiveC.title")}
      subtitle={t("company.fiveC.subtitle")}
      icon="ri-radar-line"
      bodyClassName="p-4"
      action={
        <div className="flex items-baseline gap-1.5 whitespace-nowrap rounded-md border border-background-200 bg-background-50 px-3 py-1.5">
          <span className="text-[11px] text-foreground-500">
            {t("company.fiveC.weighted")}
          </span>
          <span className="font-mono text-base font-semibold text-primary-400">
            {weighted.toFixed(1)}
          </span>
          <span className="font-mono text-[10px] text-foreground-500">
            {t("company.fiveC.weightedUnit")}
          </span>
        </div>
      }
    >
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <div className="rounded-md border border-background-200/70 bg-background-50 p-3">
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={chartData} outerRadius="70%">
                <PolarGrid stroke={chartPalette.grid} />
                <PolarAngleAxis
                  dataKey="dimension"
                  tick={{ fontSize: 12, fill: chartPalette.axis }}
                />
                <PolarRadiusAxis
                  domain={[0, 100]}
                  tick={false}
                  axisLine={false}
                />
                <Radar
                  name={t("company.fiveC.radarName")}
                  dataKey="score"
                  stroke={chartPalette.primary}
                  strokeWidth={2}
                  fill={chartPalette.primary}
                  fillOpacity={0.26}
                />
                <Tooltip content={<DimensionTooltip />} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-1 flex items-center justify-center gap-2">
            <span className="h-2 w-2 rounded-full bg-primary-500"></span>
            <span className="text-[11px] text-foreground-500">
              {t("company.fiveC.legend")}
            </span>
          </div>
        </div>

        <ul className="space-y-3.5">
          {dimensions.map((item) => (
            <li
              key={item.key}
              className="rounded-md border border-background-200/70 bg-background-50 p-3"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[13px] font-medium text-foreground-950">
                  {isEn ? item.en : item.label}
                </span>
                <span className="font-mono text-[10px] text-foreground-500">
                  {isEn ? item.label : item.en}
                </span>
                <span className="rounded bg-background-200/80 px-1.5 py-0.5 font-mono text-[10px] text-foreground-600">
                  {t("company.fiveC.weight", { weight: item.weight })}
                </span>
                <span className="ml-auto font-mono text-sm font-semibold text-foreground-950">
                  {item.score}
                </span>
              </div>
              <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-background-200">
                <span
                  className={`block h-full rounded-full ${barTone(item.score)}`}
                  style={{ width: `${item.score}%` }}
                ></span>
              </div>
              <p className="mt-2 text-xs leading-relaxed text-foreground-600">
                {pick(item.note, item.noteEn)}
              </p>
            </li>
          ))}
        </ul>
      </div>
    </Card>
  );
}