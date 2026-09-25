import { useTranslation } from "react-i18next";
import AppShell from "@/components/feature/AppShell";

interface ComingSoonProps {
  title: string;
  subtitle: string;
  icon: string;
  phase: string;
  points: string[];
}

export default function ComingSoon({
  title,
  subtitle,
  icon,
  phase,
  points,
}: ComingSoonProps) {
  const { t } = useTranslation();
  return (
    <AppShell title={title} subtitle={subtitle}>
      <div className="animate-fade-up tech-grid overflow-hidden rounded-lg border border-background-200 bg-background-100">
        <div className="flex flex-col items-center px-6 py-16 text-center">
          <span className="flex h-16 w-16 items-center justify-center rounded-lg bg-primary-500/12 text-primary-400">
            <i className={`${icon} text-3xl`}></i>
          </span>
          <h2 className="mt-5 font-heading text-lg font-semibold text-foreground-950">
            {title} · {t("comingSoon.building")}
          </h2>
          <p className="mt-2 max-w-lg text-sm leading-relaxed text-foreground-500">
            {subtitle}
          </p>

          <div className="mt-6 w-full max-w-xl rounded-md border border-background-200 bg-background-50 p-4 text-left">
            <div className="flex items-center gap-2">
              <span className="flex h-5 w-5 items-center justify-center rounded bg-accent-500/15 text-accent-400">
                <i className="ri-list-check-2 text-[13px]"></i>
              </span>
              <p className="text-xs font-medium text-foreground-800">
                {t("comingSoon.willInclude")} · {phase}
              </p>
            </div>
            <ul className="mt-3 space-y-2">
              {points.map((p) => (
                <li
                  key={p}
                  className="flex items-start gap-2 text-[13px] text-foreground-600"
                >
                  <i className="ri-checkbox-blank-circle-line mt-1 text-[8px] text-primary-400"></i>
                  <span>{p}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </AppShell>
  );
}