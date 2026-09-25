import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation } from "react-router-dom";
import PageFrame from "@/features/workbench-layout/ui/PageFrame";

export default function BenchmarkShell({ title, children }: { title: string; children: ReactNode }) {
  const { t } = useTranslation();
  const location = useLocation();
  const links = [
    { path: "/benchmark", label: t("benchmark.home") },
    { path: "/benchmark/search", label: t("benchmark.search") },
    { path: "/benchmark/model", label: t("benchmark.model") },
  ];
  return <PageFrame benchmark title={title} subtitle={t("benchmark.subtitle")}>
    <div className="space-y-5">
      <nav className="flex flex-wrap gap-2" aria-label={t("benchmark.title")}>
        {links.map(({ path, label }) => <Link key={path} to={path} className={`rounded-md border px-3 py-1.5 text-xs transition-colors ${location.pathname === path ? "border-primary-500 bg-primary-500/12 text-primary-400" : "border-background-300 text-foreground-600 hover:text-primary-400"}`}>{label}</Link>)}
      </nav>
      <div className="rounded-lg border border-accent-500/25 bg-accent-500/8 px-4 py-3 text-xs leading-relaxed text-foreground-700">{t("benchmark.disclaimer")}</div>
      {children}
    </div>
  </PageFrame>;
}
