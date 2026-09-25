import { useState } from "react";
import { useTranslation } from "react-i18next";
import Card from "@/shared/ui/Card";
import { useLang } from "@/shared/lib/useLang";
import {
  impactColorClass,
  timelineFilterOrder,
  timelineTypeIcon,
} from "@/features/demo-scenarios/lib/profile";
import type { TimelineEvent, TimelineType } from "@/entities/demo/model/types";

interface ChangeTimelineProps {
  events: TimelineEvent[];
}

const DOT_CLASS: Record<string, string> = {
  positive: "border-primary-400/50 bg-primary-500/12 text-primary-400",
  neutral: "border-background-300 bg-background-200 text-foreground-500",
  negative: "risk-border-high risk-soft-high risk-text-high",
};

export default function ChangeTimeline({ events }: ChangeTimelineProps) {
  const { t } = useTranslation();
  const { pick } = useLang();
  const [filter, setFilter] = useState<"all" | TimelineType>("all");

  const availableTypes = timelineFilterOrder.filter((type) =>
    events.some((event) => event.type === type),
  );
  const visible =
    filter === "all"
      ? events
      : events.filter((event) => event.type === filter);

  const chips: { key: "all" | TimelineType; label: string }[] = [
    { key: "all", label: t("company.timeline.all") },
    ...availableTypes.map((type) => ({
      key: type,
      label: t(`company.timeline.types.${type}`),
    })),
  ];

  return (
    <Card
      title={t("company.timeline.title")}
      subtitle={t("company.timeline.subtitle")}
      icon="ri-history-line"
      bodyClassName="p-4"
      action={
        <div className="flex flex-wrap items-center gap-1 rounded-full border border-background-200 bg-background-50 p-1">
          {chips.map((chip) => (
            <button
              key={chip.key}
              type="button"
              onClick={() => setFilter(chip.key)}
              className={`cursor-pointer whitespace-nowrap rounded-full px-2.5 py-1 text-[11px] transition-colors ${
                filter === chip.key
                  ? "bg-primary-500 font-medium text-background-50"
                  : "text-foreground-600 hover:text-foreground-900"
              }`}
            >
              {chip.label}
            </button>
          ))}
        </div>
      }
    >
      <ol>
        {visible.map((event, index) => {
          const icon = timelineTypeIcon[event.type];
          const typeLabel = t(`company.timeline.types.${event.type}`);
          const toneColor = impactColorClass[event.impact];
          const toneLabel = t(`company.timeline.impact.${event.impact}`);
          const isLast = index === visible.length - 1;

          return (
            <li key={event.id} className="flex gap-3">
              <div className="flex w-6 shrink-0 flex-col items-center">
                <span
                  className={`flex h-6 w-6 items-center justify-center rounded-full border ${DOT_CLASS[event.impact]}`}
                >
                  <i className={`${icon} text-[11px]`}></i>
                </span>
                {!isLast && (
                  <span className="mt-1 w-px flex-1 bg-background-300"></span>
                )}
              </div>

              <div className={`min-w-0 flex-1 ${isLast ? "" : "pb-5"}`}>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-[11px] text-foreground-500">
                    {event.date}
                  </span>
                  <span className="rounded bg-background-200/80 px-1.5 py-0.5 text-[10px] text-foreground-600">
                    {typeLabel}
                  </span>
                  <span className={`text-[10px] ${toneColor}`}>
                    {toneLabel}
                  </span>
                </div>
                <p className="mt-1 text-[13px] font-medium text-foreground-950">
                  {pick(event.title, event.titleEn)}
                </p>
                <p className="mt-1 text-xs leading-relaxed text-foreground-600">
                  {pick(event.desc, event.descEn)}
                </p>
              </div>
            </li>
          );
        })}
      </ol>

      {visible.length === 0 && (
        <p className="py-8 text-center text-xs text-foreground-500">
          {t("company.timeline.empty")}
        </p>
      )}
    </Card>
  );
}