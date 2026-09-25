import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { useTranslation } from "react-i18next";
import { TooltipBubble } from "@/shared/ui/Tooltip";
import { riskDistribution } from "@/features/demo-scenarios/model/fixtures/overview";
import { chartPalette } from "@/shared/config/theme/palette";

const COLOR_MAP: Record<string, string> = {
  low: chartPalette.riskLow,
  medium: chartPalette.riskMedium,
  high: chartPalette.riskHigh,
};

const total = riskDistribution.reduce((sum, item) => sum + item.value, 0);

interface TooltipItem {
  name?: string;
  value?: number;
  payload?: { level?: string };
}

interface RiskTooltipProps {
  active?: boolean;
  payload?: TooltipItem[];
}

function RiskTooltipContent({ active, payload }: RiskTooltipProps) {
  const { t } = useTranslation();
  if (!active || !payload || payload.length === 0) {
    return null;
  }
  const item = payload[0];
  const value = typeof item.value === "number" ? item.value : 0;
  const level = item.payload?.level ?? "low";
  const percent = total > 0 ? (value / total) * 100 : 0;

  return (
    <TooltipBubble>
      <div className="flex items-center gap-2">
        <span
          className="h-2 w-2 shrink-0 rounded-full"
          style={{ backgroundColor: COLOR_MAP[level] }}
        />
        <span>{t(`overview.risk.${level}`)}</span>
        <span className="font-mono">{t("common.companiesUnit", { count: value })}</span>
        <span className="font-mono text-background-200">
          {percent.toFixed(1)}%
        </span>
      </div>
    </TooltipBubble>
  );
}

export default function RiskDistributionChart() {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col items-center">
      <div className="relative h-48 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={riskDistribution}
              dataKey="value"
              nameKey="label"
              innerRadius={56}
              outerRadius={82}
              paddingAngle={3}
              stroke="none"
            >
              {riskDistribution.map((item) => (
                <Cell key={item.level} fill={COLOR_MAP[item.level]} />
              ))}
            </Pie>
            <Tooltip content={<RiskTooltipContent />} />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-mono text-xl font-semibold text-foreground-950">
            {total.toLocaleString()}
          </span>
          <span className="text-[11px] text-foreground-500">
            {t("overview.risk.centerLabel")}
          </span>
        </div>
      </div>

      <ul className="mt-4 w-full space-y-2">
        {riskDistribution.map((item) => (
          <li key={item.level} className="flex items-center gap-2.5 text-xs">
            <span
              className="h-2.5 w-2.5 rounded-full"
              style={{ backgroundColor: COLOR_MAP[item.level] }}
            ></span>
            <span className="text-foreground-600">{t(`overview.risk.${item.level}`)}</span>
            <span className="ml-auto font-mono font-medium text-foreground-900">
              {item.value.toLocaleString()}
            </span>
            <span className="w-12 text-right font-mono text-foreground-500">
              {((item.value / total) * 100).toFixed(1)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}