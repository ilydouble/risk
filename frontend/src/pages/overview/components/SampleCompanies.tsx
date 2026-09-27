import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import type { components } from "@/shared/api/generated/schema";

type OverviewSampleCompanyDTO = components["schemas"]["OverviewSampleCompanyDTO"];
type LabelCategory = OverviewSampleCompanyDTO["labelCategory"];

const TONES: Record<LabelCategory, string> = {
  healthy: "bg-primary-500/10 text-primary-500",
  distress: "bg-danger-500/10 text-danger-500",
  unlabeled: "bg-background-300/70 text-foreground-600",
};

export default function SampleCompanies({ samples }: { samples: OverviewSampleCompanyDTO[] }) {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<LabelCategory | "all">("all");
  const filtered = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    return samples.filter((item) => {
      const matchesCategory = category === "all" || item.labelCategory === category;
      const matchesQuery = !keyword || `${item.companyId} ${item.name} ${item.status}`.toLowerCase().includes(keyword);
      return matchesCategory && matchesQuery;
    });
  }, [category, query, samples]);
  const visible = filtered.slice(0, 50);

  return <div>
    <div className="flex flex-col gap-2 border-b border-background-200 p-4 sm:flex-row">
      <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t("overview.samples.search")} className="min-w-0 flex-1 rounded-md border border-background-300 bg-background-50 px-3 py-2 text-xs text-foreground-900 outline-none focus:border-primary-400" />
      <select value={category} onChange={(event) => setCategory(event.target.value as LabelCategory | "all")} className="rounded-md border border-background-300 bg-background-50 px-3 py-2 text-xs text-foreground-800 outline-none focus:border-primary-400">
        {(["all", "healthy", "distress", "unlabeled"] as const).map((value) => <option key={value} value={value}>{t(`overview.samples.category.${value}`)}</option>)}
      </select>
    </div>
    <div className="overflow-x-auto"><table className="w-full min-w-[840px] text-left text-xs">
      <thead className="border-b border-background-200 bg-background-50 text-foreground-500"><tr><th className="px-4 py-2.5">{t("overview.samples.company")}</th><th>{t("overview.samples.status")}</th><th>{t("overview.samples.categoryLabel")}</th><th>{t("overview.samples.age")}</th><th>{t("overview.samples.industry")}</th><th>{t("overview.samples.relations")}</th></tr></thead>
      <tbody>{visible.map((item) => <tr key={item.companyId} className="border-b border-background-200/60 last:border-0">
        <td className="px-4 py-3"><p className="font-medium text-foreground-900">{item.name}</p><p className="mt-0.5 font-mono text-[10px] text-foreground-500">{item.companyId}</p></td>
        <td className="max-w-64 truncate pr-4 text-foreground-700" title={item.status}>{item.status}</td>
        <td><span className={`rounded-full px-2 py-1 text-[10px] font-semibold ${TONES[item.labelCategory]}`}>{t(`overview.samples.category.${item.labelCategory}`)}</span></td>
        <td className="font-mono text-foreground-700">{item.ageYears?.toFixed(1) ?? "—"}</td><td className="font-mono text-foreground-700">{item.industryCode ?? "—"}</td><td className="font-mono text-foreground-700">{item.relationCount}</td>
      </tr>)}</tbody>
    </table></div>
    <p className="border-t border-background-200 px-4 py-3 text-[11px] text-foreground-500">{t("overview.samples.showing", { shown: visible.length, total: filtered.length })}</p>
  </div>;
}
