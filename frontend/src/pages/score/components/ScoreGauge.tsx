import { useTranslation } from "react-i18next";
import { SCORE_MAX, SCORE_MIN } from "@/pages/score/lib/score";

interface ScoreGaugeProps {
  score: number;
  color: string;
}

const RADIUS = 80;
const CENTER_X = 100;
const CENTER_Y = 100;

function pointAt(ratio: number) {
  const angle = Math.PI * (1 - ratio);
  return {
    x: CENTER_X + RADIUS * Math.cos(angle),
    y: CENTER_Y - RADIUS * Math.sin(angle),
  };
}

export default function ScoreGauge({ score, color }: ScoreGaugeProps) {
  const { t } = useTranslation();
  const ratio = Math.min(1, Math.max(0, (score - SCORE_MIN) / (SCORE_MAX - SCORE_MIN)));
  const end = pointAt(ratio);
  const path = `M ${CENTER_X - RADIUS} ${CENTER_Y} A ${RADIUS} ${RADIUS} 0 0 1 ${end.x} ${end.y}`;

  return (
    <div className="relative mx-auto w-full max-w-[240px]">
      <svg viewBox="0 0 200 118" className="w-full">
        <path
          d="M 20 100 A 80 80 0 0 1 180 100"
          fill="none"
          stroke="oklch(var(--background-300))"
          strokeWidth={11}
          strokeLinecap="round"
        />
        <path
          d={path}
          fill="none"
          stroke={color}
          strokeWidth={11}
          strokeLinecap="round"
        />
        <circle cx={end.x} cy={end.y} r={5.5} fill="oklch(var(--background-50))" stroke={color} strokeWidth={3} />
        <text x={20} y={114} textAnchor="middle" fontSize={9} fill="oklch(var(--foreground-500))">
          {SCORE_MIN}
        </text>
        <text x={180} y={114} textAnchor="middle" fontSize={9} fill="oklch(var(--foreground-500))">
          {SCORE_MAX}
        </text>
      </svg>

      <div className="absolute inset-x-0 top-[30%] flex flex-col items-center">
        <span className="font-mono text-5xl font-semibold leading-none tracking-tight text-foreground-950">
          {score}
        </span>
        <span className="mt-1 text-[11px] text-foreground-500">{t("score.gauge.label")}</span>
      </div>
    </div>
  );
}