import { useTranslation } from "react-i18next";
import Card from "@/shared/ui/Card";
import { GRADE_BANDS, formatContribution } from "@/features/demo-scenarios/lib/score";
import { chartPalette } from "@/shared/config/theme/palette";
import { useLang } from "@/shared/lib/useLang";
import type { ScoreDetail } from "@/entities/demo/model/types";

interface ModelExplainCardProps {
  detail: ScoreDetail;
}

export default function ModelExplainCard({ detail }: ModelExplainCardProps) {
  const { t } = useTranslation();
  const { isEn } = useLang();
  const positive = detail.features.filter((item) => item.contribution > 0).slice(0, 3);
  const negative = detail.features.filter((item) => item.contribution < 0).slice(-3).reverse();

  return (
    <Card
      title={t("score.explain.title")}
      subtitle={t("score.explain.subtitle")}
      icon="ri-shield-star-line"
      bodyClassName="p-4"
    >
      <div className="flex items-center gap-3 rounded-md border border-background-200/70 bg-background-50 p-3">
        <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-primary-500/12 font-mono text-lg font-semibold text-primary-400">
          {detail.grade}
        </span>
        <div className="min-w-0">
          <p className="text-[12px] font-medium text-foreground-900">
            {t("score.explain.current", { grade: detail.grade })}
          </p>
          <p className="mt-0.5 text-[11px] leading-snug text-foreground-500">
            {detail.gradeNote}
          </p>
        </div>
      </div>

      <div className="mt-3">
        <p className="mb-2 text-[11px] font-medium text-foreground-700">{t("score.explain.bands")}</p>
        <ul className="space-y-1">
          {GRADE_BANDS.map((band, index) => {
            const next = GRADE_BANDS[index - 1];
            const upper = next ? next.min - 1 : 850;
            const active = detail.grade === band.grade;
            return (
              <li
                key={band.grade}
                className={`flex items-center gap-2 rounded-md px-2.5 py-1.5 text-[11px] ${
                  active
                    ? "bg-primary-500/12 text-primary-300"
                    : "text-foreground-500"
                }`}
              >
                <span className="w-9 font-mono font-medium">{band.grade}</span>
                <span className="font-mono text-foreground-600">
                  {band.min}–{upper}
                </span>
                <span className="ml-auto truncate text-[10px] text-foreground-500">
                  {isEn ? band.noteEn : band.note}
                </span>
              </li>
            );
          })}
        </ul>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2">
        <div className="rounded-md border border-background-200/70 bg-background-50 p-2.5">
          <p className="text-[10px] text-foreground-500">{t("score.explain.posTop")}</p>
          <ul className="mt-1.5 space-y-1">
            {positive.map((item) => (
              <li key={item.id} className="flex items-center justify-between gap-2">
                <span className="truncate text-[10px] text-foreground-700">{item.label}</span>
                <span className="shrink-0 font-mono text-[10px]" style={{ color: chartPalette.primary }}>
                  {formatContribution(item.contribution)}
                </span>
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-md border border-background-200/70 bg-background-50 p-2.5">
          <p className="text-[10px] text-foreground-500">{t("score.explain.negTop")}</p>
          <ul className="mt-1.5 space-y-1">
            {negative.map((item) => (
              <li key={item.id} className="flex items-center justify-between gap-2">
                <span className="truncate text-[10px] text-foreground-700">{item.label}</span>
                <span className="shrink-0 font-mono text-[10px]" style={{ color: chartPalette.riskHigh }}>
                  {formatContribution(item.contribution)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <p className="mt-3 rounded-md border border-background-200/70 bg-background-50 p-2.5 text-[10px] leading-relaxed text-foreground-500">
        {t("score.explain.note", {
          version: detail.modelVersion,
          time: detail.evaluatedAt,
        })}
      </p>
    </Card>
  );
}