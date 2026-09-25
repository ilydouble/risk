import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { evaluationTrend } from "@/mocks/overview";
import { chartPalette } from "@/theme/palette";
import { useTranslation } from "react-i18next";

interface TooltipItem {
  name?: string;
  value?: number | string;
  color?: string;
}

interface TooltipProps {
  active?: boolean;
  payload?: TooltipItem[];
  label?: string | number;
}

function TrendTooltip({ active, payload, label }: TooltipProps) {
  if (!active || !payload || payload.length === 0) {
    return null;
  }
  return (
    <div className="rounded-md border border-background-300 bg-background-100 px-3 py-2">
      <p className="font-mono text-[11px] text-foreground-500">{label}</p>
      {payload.map((item) => (
        <p
          key={String(item.name)}
          className="mt-1 flex items-center gap-2 text-xs text-foreground-900"
        >
          <span
            className="h-2 w-2 rounded-full"
            style={{ backgroundColor: item.color }}
          ></span>
          <span className="text-foreground-500">{item.name}</span>
          <span className="ml-auto font-mono font-medium">{item.value}</span>
        </p>
      ))}
    </div>
  );
}

interface EvaluationTrendChartProps {
  range: number;
}

export default function EvaluationTrendChart({
  range,
}: EvaluationTrendChartProps) {
  const { t } = useTranslation();
  const data = evaluationTrend.slice(-range);

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 12, right: 8, left: -18, bottom: 0 }}>
          <defs>
            <linearGradient id="fillEvaluations" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={chartPalette.primary} stopOpacity={0.42} />
              <stop offset="100%" stopColor={chartPalette.primary} stopOpacity={0} />
            </linearGradient>
            <linearGradient id="fillHighRisk" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={chartPalette.accent} stopOpacity={0.34} />
              <stop offset="100%" stopColor={chartPalette.accent} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={chartPalette.grid} strokeDasharray="3 6" vertical={false} />
          <XAxis
            dataKey="date"
            stroke={chartPalette.axis}
            tick={{ fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            stroke={chartPalette.axis}
            tick={{ fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip content={<TrendTooltip />} cursor={{ stroke: chartPalette.grid }} />
          <Area
            type="monotone"
            dataKey="evaluations"
            name={t("overview.chart.seriesEvaluations")}
            stroke={chartPalette.primary}
            strokeWidth={2}
            fill="url(#fillEvaluations)"
          />
          <Area
            type="monotone"
            dataKey="highRisk"
            name={t("overview.chart.seriesHighRisk")}
            stroke={chartPalette.accent}
            strokeWidth={2}
            fill="url(#fillHighRisk)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}