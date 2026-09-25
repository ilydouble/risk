import { useMemo, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import Card from "@/shared/ui/Card";
import { formatContribution } from "@/features/demo-scenarios/lib/score";
import { chartPalette } from "@/shared/config/theme/palette";
import type { ShapFeature } from "@/entities/demo/model/types";

interface ShapWaterfallProps {
  features: ShapFeature[];
  baseValue: number;
  finalScore: number;
}

interface DeltaRow {
  feature: ShapFeature;
  from: number;
  to: number;
}

export default function ShapWaterfall({
  features,
  baseValue,
  finalScore,
}: ShapWaterfallProps) {
  const { t } = useTranslation();
  const { rows, toPercent, ticks } = useMemo(() => {
    const deltas: DeltaRow[] = [];
    let running = baseValue;
    features.forEach((feature) => {
      const from = running;
      const to = running + feature.contribution;
      deltas.push({ feature, from, to });
      running = to;
    });

    const values = [baseValue, finalScore, ...deltas.map((row) => row.from), ...deltas.map((row) => row.to)];
    const minValue = Math.min(...values);
    const maxValue = Math.max(...values);
    const pad = (maxValue - minValue) * 0.12 || 30;
    const low = minValue - pad;
    const high = maxValue + pad;

    const tickList = Array.from({ length: 5 }, (_, index) =>
      Math.round(low + ((high - low) * index) / 4),
    );

    return {
      rows: deltas,
      ticks: tickList,
      toPercent: (value: number) => ((value - low) / (high - low)) * 100,
    };
  }, [features, baseValue, finalScore]);

  const baseLeft = toPercent(Math.min(baseValue, finalScore));
  const baseWidth = Math.abs(toPercent(baseValue) - baseLeft) || 0.4;

  return (
    <Card
      title={t("score.waterfall.title")}
      subtitle={t("score.waterfall.subtitle", { base: baseValue, final: finalScore })}
      icon="ri-water-flash-line"
      bodyClassName="p-4"
      action={
        <div className="flex items-center gap-3 whitespace-nowrap">
          <span className="flex items-center gap-1.5 text-[10px] text-foreground-500">
            <span className="h-2 w-3 rounded-sm bg-primary-500"></span>
            {t("score.waterfall.positive")}
          </span>
          <span className="flex items-center gap-1.5 text-[10px] text-foreground-500">
            <span className="h-2 w-3 rounded-sm" style={{ backgroundColor: chartPalette.riskHigh }}></span>
            {t("score.waterfall.negative")}
          </span>
        </div>
      }
    >
      <div className="overflow-x-auto">
        <div className="min-w-[560px] space-y-1.5">
          <RowShell label={t("score.waterfall.baseRow")} value={String(baseValue)} tone="text-foreground-700">
            <div className="relative h-6">
              <span
                className="absolute top-0 h-full rounded-sm bg-secondary-500/50"
                style={{ left: `${baseLeft}%`, width: `${baseWidth}%` }}
              ></span>
              <Connector left={toPercent(baseValue)} />
            </div>
          </RowShell>

          {rows.map((row) => {
            const isPositive = row.feature.contribution >= 0;
            const left = toPercent(Math.min(row.from, row.to));
            const width = Math.abs(toPercent(row.to) - toPercent(row.from)) || 0.4;
            const color = isPositive ? chartPalette.primary : chartPalette.riskHigh;

            return (
              <RowShell
                key={row.feature.id}
                label={row.feature.label}
                value={formatContribution(row.feature.contribution)}
                tone={isPositive ? "text-primary-400" : "risk-text-high"}
              >
                <div
                  className="group relative h-6"
                  title={`${row.feature.label}：${row.feature.value} · ${formatContribution(row.feature.contribution)}`}
                >
                  <span
                    className="absolute top-0 h-full rounded-sm transition-opacity group-hover:opacity-80"
                    style={{
                      left: `${left}%`,
                      width: `${width}%`,
                      backgroundColor: color,
                      opacity: 0.88,
                    }}
                  ></span>
                  <Connector left={toPercent(row.to)} />
                </div>
              </RowShell>
            );
          })}

          <RowShell
            label={t("score.waterfall.finalRow")}
            value={String(finalScore)}
            tone="text-foreground-950"
            emphasis
          >
            <div className="relative h-6">
              <span
                className="absolute top-0 h-full rounded-sm bg-primary-500"
                style={{ left: `${baseLeft}%`, width: `${Math.abs(toPercent(finalScore) - baseLeft)}%` }}
              ></span>
            </div>
          </RowShell>

          <div className="grid grid-cols-[136px_minmax(0,1fr)_64px] items-center gap-2 pt-1.5">
            <span></span>
            <div className="relative h-4">
              {ticks.map((tick) => (
                <span
                  key={tick}
                  className="absolute -translate-x-1/2 font-mono text-[10px] text-foreground-500"
                  style={{ left: `${toPercent(tick)}%` }}
                >
                  {tick}
                </span>
              ))}
            </div>
            <span></span>
          </div>
        </div>
      </div>

      <p className="mt-3 rounded-md border border-background-200/70 bg-background-50 p-3 text-[11px] leading-relaxed text-foreground-500">
        {t("score.waterfall.note", { base: baseValue, final: finalScore })}
      </p>
    </Card>
  );
}

interface RowShellProps {
  label: string;
  value: string;
  tone: string;
  emphasis?: boolean;
  children: ReactNode;
}

function RowShell({ label, value, tone, emphasis, children }: RowShellProps) {
  return (
    <div className="grid grid-cols-[136px_minmax(0,1fr)_64px] items-center gap-2">
      <span
        className={`truncate text-[11px] ${emphasis ? "font-semibold text-foreground-900" : "text-foreground-600"}`}
        title={label}
      >
        {label}
      </span>
      <div className="rounded bg-background-50">{children}</div>
      <span className={`text-right font-mono text-[11px] font-medium ${tone}`}>{value}</span>
    </div>
  );
}

function Connector({ left }: { left: number }) {
  return (
    <span
      className="pointer-events-none absolute top-0 h-[calc(100%+6px)] border-l border-dashed border-background-400/70"
      style={{ left: `${left}%` }}
    ></span>
  );
}