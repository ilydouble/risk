import { useTranslation } from "react-i18next";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { components } from "@/shared/api/generated/schema";
import { chartPalette } from "@/shared/config/theme/palette";

type AgeDistributionItemDTO = components["schemas"]["AgeDistributionItemDTO"];

export default function AgeDistributionChart({ data }: { data: AgeDistributionItemDTO[] }) {
  const { t } = useTranslation();
  const rows = data.map((item) => ({
    ...item,
    label: t(`overview.age.bucket.${item.bucket}`),
  }));
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 12, right: 12, left: 6, bottom: 0 }}>
          <CartesianGrid stroke={chartPalette.grid} strokeDasharray="3 6" vertical={false} />
          <XAxis dataKey="label" stroke={chartPalette.axis} tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis stroke={chartPalette.axis} tick={{ fontSize: 11 }} axisLine={false} tickLine={false} width={54} />
          <Tooltip formatter={(value) => Number(value).toLocaleString()} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Bar dataKey="total" name={t("overview.age.total")} fill={chartPalette.primary} radius={[3, 3, 0, 0]} />
          <Bar dataKey="labeled" name={t("overview.age.labeled")} fill={chartPalette.secondary} radius={[3, 3, 0, 0]} />
          <Bar dataKey="distress" name={t("overview.age.distress")} fill={chartPalette.accent} radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
