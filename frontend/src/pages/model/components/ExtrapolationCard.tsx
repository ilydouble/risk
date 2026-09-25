import {
  Bar,
  BarChart,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useTranslation } from "react-i18next";
import Card from "@/components/base/Card";
import { chartPalette } from "@/theme/palette";
import { cohortLabel } from "@/pages/model/lib/eval";
import { useLang } from "@/hooks/useLang";
import type { ExtrapolationCohort, ExtrapolationRow, ExtrapolationStudy } from "@/types";

interface ExtrapolationCardProps {
  study: ExtrapolationStudy;
  onReproduce: () => void;
}

const COHORT_COLOR: Record<ExtrapolationCohort, string> = {
  in: chartPalette.primary,
  near: chartPalette.accent,
  far: chartPalette.riskHigh,
};

const COHORT_CLASS: Record<ExtrapolationCohort, string> = {
  in: "border-primary-400/40 bg-primary-500/12 text-primary-400",
  near: "border-accent-500/40 bg-accent-500/12 text-accent-400",
  far: "risk-border-high risk-soft-high risk-text-high",
};

interface TooltipItem {
  payload?: ExtrapolationRow;
}

interface TooltipProps {
  active?: boolean;
  payload?: TooltipItem[];
}

function ExtrapolationTooltip({ active, payload }: TooltipProps) {
  const { t } = useTranslation();
  const { lang } = useLang();
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  return (
    <div className="rounded-md border border-background-300 bg-background-100 px-3 py-2">
      <p className="text-[12px] font-medium text-foreground-900">{row.region}</p>
      <p className="mt-0.5 text-[10px] text-foreground-500">
        {cohortLabel(lang)[row.cohort]} ·{" "}
        {t("model.extrapolation.sample", { value: row.sampleSize.toLocaleString("en-US") })}
      </p>
      <div className="mt-1.5 space-y-1 text-[11px]">
        <p className="flex items-center justify-between gap-4">
          <span className="text-foreground-500">AUC</span>
          <span className="font-mono text-foreground-900">
            {row.auc.toFixed(3)}{" "}
            <span className={row.aucDecay < 0 ? "risk-text-high" : "text-primary-400"}>
              ({row.aucDecay.toFixed(3)})
            </span>
          </span>
        </p>
        <p className="flex items-center justify-between gap-4">
          <span className="text-foreground-500">KS</span>
          <span className="font-mono text-foreground-900">{row.ks.toFixed(3)}</span>
        </p>
        <p className="flex items-center justify-between gap-4">
          <span className="text-foreground-500">PSI</span>
          <span className="font-mono text-foreground-900">{row.psi.toFixed(2)}</span>
        </p>
      </div>
    </div>
  );
}

export default function ExtrapolationCard({
  study,
  onReproduce,
}: ExtrapolationCardProps) {
  const { t } = useTranslation();
  const { lang } = useLang();
  const labels = cohortLabel(lang);

  const psiBands = [
    { range: "PSI < 0.10", note: t("model.extrapolation.psiOk"), tone: "primary" },
    { range: "0.10 – 0.25", note: t("model.extrapolation.psiWatch"), tone: "accent" },
    { range: "PSI > 0.25", note: t("model.extrapolation.psiAlert"), tone: "high" },
  ];

  return (
    <Card
      className="animate-fade-up"
      title={t("model.extrapolation.title")}
      subtitle={t("model.extrapolation.subtitle", { count: study.rows.length })}
      icon="ri-earth-line"
      bodyClassName="p-4"
      action={
        <button
          type="button"
          onClick={onReproduce}
          className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border border-background-300 px-2.5 py-1.5 text-[11px] text-foreground-600 transition-colors hover:border-primary-400 hover:text-primary-400"
        >
          <i className="ri-refresh-line text-[13px]"></i>
          {t("model.extrapolation.reproduce")}
        </button>
      }
    >
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_300px]">
        <div>
          <div className="flex flex-wrap items-center gap-4 px-1 pb-2 text-[11px]">
            {(Object.keys(COHORT_COLOR) as ExtrapolationCohort[]).map((key) => (
              <span key={key} className="flex items-center gap-1.5">
                <span
                  className="h-2.5 w-2.5 rounded-sm"
                  style={{ backgroundColor: COHORT_COLOR[key] }}
                ></span>
                <span className="text-foreground-600">{labels[key]}</span>
              </span>
            ))}
            <span className="flex items-center gap-1.5">
              <span className="h-0.5 w-4 rounded-full border-t border-dashed border-background-400"></span>
              <span className="text-foreground-600">
                {t("model.extrapolation.baseline", { value: study.baselineAuc.toFixed(3) })}
              </span>
            </span>
          </div>

          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                layout="vertical"
                data={study.rows}
                margin={{ top: 8, right: 20, left: 6, bottom: 0 }}
              >
                <XAxis
                  type="number"
                  domain={[0.78, 0.9]}
                  ticks={[0.78, 0.82, 0.86, 0.9]}
                  stroke={chartPalette.axis}
                  tick={{ fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(value: number) => value.toFixed(2)}
                />
                <YAxis
                  type="category"
                  dataKey="short"
                  width={98}
                  stroke={chartPalette.axis}
                  tick={{ fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  cursor={{ fill: chartPalette.primarySoft }}
                  content={<ExtrapolationTooltip />}
                />
                <ReferenceLine
                  x={study.baselineAuc}
                  stroke={chartPalette.axis}
                  strokeDasharray="4 4"
                />
                <Bar dataKey="auc" radius={[0, 4, 4, 0]} barSize={16}>
                  {study.rows.map((row) => (
                    <Cell key={row.id} fill={COHORT_COLOR[row.cohort]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="flex flex-col gap-3">
          <div className="rounded-md border border-background-200 bg-background-50 p-4">
            <p className="flex items-center gap-1.5 text-[11px] font-medium text-foreground-700">
              <i className="ri-guide-line text-[13px] text-foreground-500"></i>
              {t("model.extrapolation.psiTitle")}
            </p>
            <ul className="mt-2 space-y-2">
              {psiBands.map((item) => (
                <li key={item.range} className="flex items-center gap-2 text-[11px]">
                  <span
                    className={`rounded px-1.5 py-0.5 font-mono text-[10px] ${
                      item.tone === "primary"
                        ? "bg-primary-500/12 text-primary-400"
                        : item.tone === "accent"
                          ? "bg-accent-500/12 text-accent-400"
                          : "risk-soft-high risk-text-high"
                    }`}
                  >
                    {item.range}
                  </span>
                  <span className="text-foreground-500">{item.note}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-md border border-background-200 bg-background-50 p-4">
            <p className="text-[11px] text-foreground-500">{t("model.extrapolation.maxDecay")}</p>
            <p className="mt-1.5 text-[14px] font-semibold text-foreground-950">
              {study.rows[study.rows.length - 1]?.region}
            </p>
            <p className="mt-1 font-mono text-lg font-semibold text-foreground-950">
              {study.rows[study.rows.length - 1]?.aucDecay.toFixed(3)}
              <span className="ml-1 text-[11px] font-normal text-foreground-500">
                AUC
              </span>
            </p>
            <p className="mt-1.5 text-[11px] leading-relaxed text-foreground-500">
              {t("model.extrapolation.maxDecayNote")}
            </p>
          </div>
        </div>
      </div>

      <div className="mt-4 overflow-x-auto rounded-md border border-background-200">
        <table className="w-full min-w-[760px] border-collapse">
          <thead>
            <tr className="border-b border-background-200/70 text-left">
              <th className="px-4 py-2.5 text-[11px] font-medium text-foreground-500">
                {t("model.extrapolation.colRegion")}
              </th>
              <th className="px-4 py-2.5 text-[11px] font-medium text-foreground-500">
                {t("model.extrapolation.colCohort")}
              </th>
              <th className="px-4 py-2.5 text-[11px] font-medium text-foreground-500">
                {t("model.extrapolation.colSample")}
              </th>
              <th className="px-4 py-2.5 text-[11px] font-medium text-foreground-500">
                {t("model.extrapolation.colAuc")}
              </th>
              <th className="px-4 py-2.5 text-[11px] font-medium text-foreground-500">
                {t("model.extrapolation.colKs")}
              </th>
              <th className="px-4 py-2.5 text-[11px] font-medium text-foreground-500">
                {t("model.extrapolation.colDecay")}
              </th>
              <th className="px-4 py-2.5 text-[11px] font-medium text-foreground-500">
                {t("model.extrapolation.colPsi")}
              </th>
              <th className="px-4 py-2.5 text-[11px] font-medium text-foreground-500">
                {t("model.extrapolation.colDecision")}
              </th>
            </tr>
          </thead>
          <tbody>
            {study.rows.map((row) => (
              <tr
                key={row.id}
                className="border-b border-background-200/50 transition-colors last:border-0 hover:bg-background-50"
              >
                <td className="px-4 py-2.5 text-[12px] font-medium text-foreground-900">
                  {row.region}
                </td>
                <td className="px-4 py-2.5">
                  <span
                    className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] ${COHORT_CLASS[row.cohort]}`}
                  >
                    {labels[row.cohort]}
                  </span>
                </td>
                <td className="px-4 py-2.5 font-mono text-[11px] text-foreground-700">
                  {row.sampleSize.toLocaleString("en-US")}
                </td>
                <td className="px-4 py-2.5 font-mono text-[11px] text-foreground-800">
                  {row.auc.toFixed(3)}
                </td>
                <td className="px-4 py-2.5 font-mono text-[11px] text-foreground-700">
                  {row.ks.toFixed(3)}
                </td>
                <td className="px-4 py-2.5">
                  <span
                    className={`font-mono text-[11px] ${
                      row.aucDecay < 0 ? "risk-text-high" : "text-primary-400"
                    }`}
                  >
                    {row.aucDecay.toFixed(3)}
                  </span>
                </td>
                <td className="px-4 py-2.5 font-mono text-[11px] text-foreground-700">
                  {row.psi.toFixed(2)}
                </td>
                <td className="px-4 py-2.5 text-[11px] text-foreground-600">
                  {row.decision}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}