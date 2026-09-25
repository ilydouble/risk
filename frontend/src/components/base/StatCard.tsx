import { Link } from "react-router-dom";

interface StatCardProps {
  icon: string;
  label: string;
  value: string;
  unit?: string;
  delta?: string;
  tone?: "primary" | "accent" | "secondary";
  delay?: number;
  to?: string;
}

const TONE_MAP: Record<"primary" | "accent" | "secondary", string> = {
  primary: "bg-primary-500/12 text-primary-400",
  accent: "bg-accent-500/12 text-accent-400",
  secondary: "bg-secondary-500/14 text-secondary-400",
};

export default function StatCard({
  icon,
  label,
  value,
  unit,
  delta,
  tone = "primary",
  delay = 0,
  to,
}: StatCardProps) {
  const inner = (
    <div
      className="group relative overflow-hidden rounded-lg border border-background-200 bg-background-100 p-4 transition-colors duration-300 hover:border-background-300"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="flex items-start justify-between">
        <span
          className={`flex h-9 w-9 items-center justify-center rounded-md ${TONE_MAP[tone]}`}
        >
          <i className={`${icon} text-[17px]`}></i>
        </span>
        {delta && (
          <span className="rounded-full bg-background-200/70 px-2 py-0.5 font-mono text-[11px] text-foreground-500">
            {delta}
          </span>
        )}
      </div>
      <p className="mt-3.5 text-xs font-medium text-foreground-500">{label}</p>
      <p className="mt-1 flex items-baseline gap-1">
        <span className="font-mono text-2xl font-semibold tracking-tight text-foreground-950">
          {value}
        </span>
        {unit && <span className="text-xs text-foreground-500">{unit}</span>}
      </p>
      <span className="pointer-events-none absolute -right-6 -top-6 h-20 w-20 rounded-full bg-primary-500/10 opacity-0 blur-2xl transition-opacity duration-300 group-hover:opacity-100"></span>
    </div>
  );

  if (to) {
    return (
      <Link to={to} className="animate-fade-up block cursor-pointer">
        {inner}
      </Link>
    );
  }

  return <div className="animate-fade-up">{inner}</div>;
}