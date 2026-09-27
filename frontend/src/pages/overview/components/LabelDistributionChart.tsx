import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { useTranslation } from "react-i18next";
import type { components } from "@/shared/api/generated/schema";
import { chartPalette } from "@/shared/config/theme/palette";

type DistributionItemDTO = components["schemas"]["DistributionItemDTO"];

const COLORS = {
  healthy: chartPalette.riskLow,
  distress: chartPalette.riskHigh,
  unlabeled: chartPalette.axis,
};

export default function LabelDistributionChart({ data }: { data: DistributionItemDTO[] }) {
  const { t } = useTranslation();
  const total = data.reduce((sum, item) => sum + item.value, 0);
  return (
    <div className="flex flex-col items-center">
      <div className="relative h-48 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="key" innerRadius={56} outerRadius={82} paddingAngle={2} stroke="none">
              {data.map((item) => <Cell key={item.key} fill={COLORS[item.key]} />)}
            </Pie>
            <Tooltip formatter={(value) => Number(value).toLocaleString()} />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <strong className="font-mono text-xl text-foreground-950">{total.toLocaleString()}</strong>
          <span className="text-[11px] text-foreground-500">{t("overview.labels.total")}</span>
        </div>
      </div>
      <ul className="mt-4 w-full space-y-2">
        {data.map((item) => <li key={item.key} className="flex items-center gap-2 text-xs">
          <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: COLORS[item.key] }} />
          <span className="text-foreground-600">{t(`overview.labels.${item.key}`)}</span>
          <span className="ml-auto font-mono text-foreground-900">{item.value.toLocaleString()}</span>
          <span className="w-12 text-right font-mono text-foreground-500">{((item.value / total) * 100).toFixed(1)}%</span>
        </li>)}
      </ul>
    </div>
  );
}
