import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useTranslation } from "react-i18next";
import Card from "@/components/base/Card";
import { chartPalette } from "@/theme/palette";
import type { CalibrationBin, CalibrationCurve } from "@/types";

interface CalibrationCardProps {
  curve: CalibrationCurve;
  onReproduce: () => void;
}

interface TooltipItem {
  payload?: CalibrationBin;
}

interface TooltipProps {
  active?: boolean;
  payload?: TooltipItem[];
}

function CalibrationTooltip({ active, payload }: TooltipProps) {
  const { t } = useTranslation();
  const bin = payload?.[0]?.payload;
  if (!active || !bin) return null;
  return (
    <div className="rounded-md border border-background-300 bg-background-100 px-3 py-2">
      <p className="font-mono text-[11px] text-foreground-500">
        {t("model.calibration.tooltipBin", { label: bin.label })}
      </p>
      <div className="mt-1.5 space-y-1 text-[11px]">
        <p className="flex items-center gap-2">
          <span
            className="h-2 w-2 rounded-full"
            style={{ backgroundColor: chartPalette.primary }}
          ></span>
          <span className="text-foreground-500">{t("model.calibration.tooltipCalibrated")}</span>
          <span className="ml-auto font-mono text-foreground-900">
            {bin.calibrated.toFixed(3)}
          </span>
        </p>
        <p className="flex items-center gap-2">
          <span
            className="h-2 w-2 rounded-full"
            style={{ backgroundColor: chartPalette.accent }}
          ></span>
          <span className="text-foreground-500">{t("model.calibration.tooltipRaw")}</span>
          <span className="ml-auto font-mono text-foreground-900">
            {bin.raw.toFixed(3)}
          </span>
        </p>
        <p className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-background-400"></span>
          <span className="text-foreground-500">{t("model.calibration.tooltipCenter")}</span>
          <span className="ml-auto font-mono text-foreground-900">
            {bin.center.toFixed(3)}
          </span>
        </p>
        <p className="flex items-center gap-2 border-t border-background-200/70 pt-1">
          <span className="text-foreground-500">{t("model.calibration.tooltipCount")}</span>
          <span className="ml-auto font-mono text-foreground-700">
            {bin.count.toLocaleString("en-US")}
          </span>
        </p>
      </div>
    </div>
  );
}

export default function CalibrationCard({
  curve,
  onReproduce,
}: CalibrationCardProps) {
  const { t } = useTranslation();
  const reduction =
    curve.rawEce > 0
      ? Math.round(((curve.rawEce - curve.ece) / curve.rawEce) * 100)
      : 0;

  const stats: { label: string; value: string; hint: string }[] = [
    { label: t("model.calibration.eceAfter"), value: curve.ece.toFixed(4), hint: t("model.calibration.eceAfterHint") },
    { label: t("model.calibration.eceBefore"), value: curve.rawEce.toFixed(4), hint: t("model.calibration.eceBeforeHint") },
    { label: t("model.calibration.mce"), value: curve.mce.toFixed(4), hint: t("model.calibration.mceHint") },
    { label: t("model.calibration.brier"), value: curve.brier.toFixed(3), hint: t("model.calibration.brierHint") },
  ];

  return (
    <Card
      className="animate-fade-up"
      title={t("model.calibration.title")}
      subtitle={t("model.calibration.subtitle")}
      icon="ri-function-line"
      bodyClassName="p-4"
      action={
        <button
          type="button"
          onClick={onReproduce}
          className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border border-background-300 px-2.5 py-1.5 text-[11px] text-foreground-600 transition-colors hover:border-primary-400 hover:text-primary-400"
        >
          <i className="ri-refresh-line text-[13px]"></i>
          {t("model.calibration.reproduce")}
        </button>
      }
    >
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_280px]">
        <div>
          <div className="flex flex-wrap items-center gap-4 px-1 pb-2 text-[11px]">
            <span className="flex items-center gap-1.5">
              <span
                className="h-0.5 w-4 rounded-full"
                style={{ backgroundColor: chartPalette.primary }}
              ></span>
              <span className="text-foreground-600">{t("model.calibration.legendCalibrated")}</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span
                className="h-0.5 w-4 rounded-full"
                style={{ backgroundColor: chartPalette.accent }}
              ></span>
              <span className="text-foreground-600">{t("model.calibration.legendRaw")}</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-0.5 w-4 rounded-full border-t border-dashed border-background-400"></span>
              <span className="text-foreground-600">{t("model.calibration.legendIdeal")}</span>
            </span>
          </div>

          <div className="h-64 w-full sm:h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={curve.bins}
                margin={{ top: 12, right: 14, left: -16, bottom: 4 }}
              >
                <CartesianGrid
                  stroke={chartPalette.grid}
                  strokeDasharray="3 6"
                />
                <XAxis
                  type="number"
                  dataKey="center"
                  domain={[0, 1]}
                  ticks={[0, 0.2, 0.4, 0.6, 0.8, 1]}
                  stroke={chartPalette.axis}
                  tick={{ fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(value: number) => value.toFixed(1)}
                />
                <YAxis
                  type="number"
                  domain={[0, 1]}
                  ticks={[0, 0.2, 0.4, 0.6, 0.8, 1]}
                  stroke={chartPalette.axis}
                  tick={{ fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(value: number) => value.toFixed(1)}
                />
                <Tooltip content={<CalibrationTooltip />} />
                <ReferenceLine
                  segment={[
                    { x: 0, y: 0 },
                    { x: 1, y: 1 },
                  ]}
                  stroke={chartPalette.axis}
                  strokeDasharray="4 4"
                />
                <Line
                  type="monotone"
                  dataKey="raw"
                  stroke={chartPalette.accent}
                  strokeWidth={2}
                  strokeDasharray="5 3"
                  dot={{ r: 2.5, fill: chartPalette.accent, strokeWidth: 0 }}
                  activeDot={{ r: 4 }}
                />
                <Line
                  type="monotone"
                  dataKey="calibrated"
                  stroke={chartPalette.primary}
                  strokeWidth={2.5}
                  dot={{ r: 3, fill: chartPalette.primary, strokeWidth: 0 }}
                  activeDot={{ r: 5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="flex flex-col gap-3">
          <div className="rounded-md border border-primary-400/25 bg-primary-500/8 p-4">
            <p className="text-[11px] text-foreground-500">{t("model.calibration.reduction")}</p>
            <div className="mt-1 flex items-baseline gap-2">
              <span className="font-mono text-3xl font-semibold text-foreground-950">
                {reduction}%
              </span>
              <span className="text-[11px] text-foreground-500">
                {curve.rawEce.toFixed(4)} → {curve.ece.toFixed(4)}
              </span>
            </div>
            <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-background-200">
              <div
                className="h-full rounded-full bg-primary-500"
                style={{ width: `${reduction}%` }}
              ></div>
            </div>
            <p className="mt-3 text-[11px] leading-relaxed text-foreground-500">
              {t("model.calibration.reductionNote")}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {stats.map((item) => (
              <div
                key={item.label}
                className="rounded-md border border-background-200 bg-background-50 p-3"
              >
                <p className="text-[10px] text-foreground-500">{item.label}</p>
                <p className="mt-1 font-mono text-lg font-semibold text-foreground-950">
                  {item.value}
                </p>
                <p className="mt-0.5 text-[10px] leading-snug text-foreground-500">
                  {item.hint}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Card>
  );
}