import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useTranslation } from "react-i18next";
import Card from "@/shared/ui/Card";
import { chartPalette } from "@/shared/config/theme/palette";
import { useLang } from "@/shared/lib/useLang";
import type { Company, CommunityBenchmark } from "@/entities/demo/model/types";

interface CommunityComparisonProps {
  company: Company;
  benchmarks: CommunityBenchmark[];
}

interface TooltipEntry {
  payload?: CommunityBenchmark;
}

function barColor(avgScore: number): string {
  if (avgScore >= 720) return chartPalette.riskLow;
  if (avgScore >= 640) return chartPalette.riskMedium;
  return chartPalette.riskHigh;
}

function BenchmarkTooltip({ payload }: TooltipEntry) {
  const { t } = useTranslation();
  const item = payload?.[0]?.payload;
  if (!item) return null;
  return (
    <div className="rounded-md border border-background-300 bg-background-100 px-3 py-2">
      <p className="text-[11px] text-foreground-500">
        {item.label} · {item.tag}
      </p>
      <p className="mt-1 font-mono text-sm font-semibold text-foreground-950">
        {t("score.community.avg")} {item.avgScore}
      </p>
      <p className="mt-0.5 font-mono text-[11px] text-foreground-500">
        {t("score.community.defaultRate")} {item.avgDefaultProb.toFixed(1)}% ·{" "}
        {t("score.community.sample", { count: item.sampleSize })}
      </p>
    </div>
  );
}

export default function CommunityComparison({ company, benchmarks }: CommunityComparisonProps) {
  const { t } = useTranslation();
  const { isEn } = useLang();

  return (
    <Card
      title={t("score.community.title")}
      subtitle={t("score.community.subtitle", { score: company.creditScore })}
      icon="ri-group-line"
      bodyClassName="p-4"
      action={
        <span className="whitespace-nowrap rounded-full bg-background-200/80 px-2.5 py-1 font-mono text-[10px] text-foreground-600">
          {t("score.community.snapshot")}
        </span>
      }
    >
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="rounded-md border border-background-200/70 bg-background-50 p-3">
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={benchmarks} margin={{ top: 16, right: 12, left: -14, bottom: 0 }}>
                <CartesianGrid stroke={chartPalette.grid} strokeDasharray="3 6" vertical={false} />
                <XAxis
                  dataKey="label"
                  stroke={chartPalette.axis}
                  tick={{ fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  domain={[400, 850]}
                  stroke={chartPalette.axis}
                  tick={{ fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip content={<BenchmarkTooltip />} cursor={{ fill: "transparent" }} />
                <ReferenceLine
                  y={company.creditScore}
                  stroke={chartPalette.primary}
                  strokeDasharray="5 5"
                  strokeWidth={1.5}
                />
                <Bar dataKey="avgScore" name={t("score.community.barName")} radius={[4, 4, 0, 0]} maxBarSize={56}>
                  {benchmarks.map((item) => (
                    <Cell key={item.key} fill={barColor(item.avgScore)} fillOpacity={0.82} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-1 flex items-center justify-center gap-4">
            <span className="flex items-center gap-1.5 text-[10px] text-foreground-500">
              <span className="h-2 w-3 rounded-sm" style={{ backgroundColor: chartPalette.riskLow }}></span>
              {t("score.community.legendHigh")}
            </span>
            <span className="flex items-center gap-1.5 text-[10px] text-foreground-500">
              <span className="h-2 w-3 rounded-sm" style={{ backgroundColor: chartPalette.riskMedium }}></span>
              {t("score.community.legendMid")}
            </span>
            <span className="flex items-center gap-1.5 text-[10px] text-foreground-500">
              <span className="h-2 w-3 rounded-sm" style={{ backgroundColor: chartPalette.riskHigh }}></span>
              {t("score.community.legendLow")}
            </span>
          </div>
        </div>

        <ul className="space-y-3">
          {benchmarks.map((item) => (
            <li
              key={item.key}
              className="rounded-md border border-background-200/70 bg-background-50 p-3"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[12px] font-medium text-foreground-950">{item.label}</span>
                <span className="rounded-full bg-background-200/80 px-2 py-0.5 text-[10px] text-foreground-600">
                  {item.tag}
                </span>
                <span className="ml-auto font-mono text-[10px] text-foreground-500">
                  {t("score.community.sample", { count: item.sampleSize })}
                </span>
              </div>

              <div className="mt-2 flex items-center gap-3 font-mono text-[11px]">
                <span className="text-foreground-500">
                  {t("score.community.avg")}{" "}
                  <span className="text-foreground-900">{item.avgScore}</span>
                </span>
                <span className="text-foreground-500">
                  {t("score.community.defaultRate")}{" "}
                  <span className="text-foreground-900">{item.avgDefaultProb.toFixed(1)}%</span>
                </span>
                <span
                  className={`ml-auto font-medium ${
                    item.diff >= 0 ? "text-primary-400" : "risk-text-high"
                  }`}
                >
                  {item.diff >= 0 ? "+" : ""}
                  {item.diff} {isEn ? "pts" : "分"}
                </span>
              </div>

              <div className="mt-2.5">
                <div className="flex items-center justify-between text-[10px] text-foreground-500">
                  <span>{t("score.community.percentiles")}</span>
                  <span className="font-mono">P{item.percentile}</span>
                </div>
                <div className="relative mt-1 h-1.5 w-full overflow-hidden rounded-full bg-background-200">
                  <span
                    className="block h-full rounded-full bg-primary-500"
                    style={{ width: `${item.percentile}%` }}
                  ></span>
                </div>
              </div>

              <p className="mt-2 text-[10px] leading-relaxed text-foreground-500">
                {t(
                  item.diff >= 0 ? "score.community.tipHigh" : "score.community.tipLow",
                  { rate: item.goodRate, pct: item.percentile },
                )}
              </p>
            </li>
          ))}
        </ul>
      </div>
    </Card>
  );
}