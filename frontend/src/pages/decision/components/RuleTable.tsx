import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import Card from "@/shared/ui/Card";
import { ruleSeverityMeta } from "@/pages/decision/lib/decision";
import { useLang } from "@/shared/lib/useLang";
import type { DecisionDoc, DecisionRule } from "@/entities/demo/model/types";

interface RuleTableProps {
  decision: DecisionDoc;
}

type FilterKey = "all" | "hit" | "pass";

export default function RuleTable({ decision }: RuleTableProps) {
  const { t } = useTranslation();
  const { isEn } = useLang();
  const [filter, setFilter] = useState<FilterKey>("all");

  const filters: { key: FilterKey; label: string; count: number }[] = [
    { key: "all", label: t("decision.rules.filterAll"), count: decision.rules.length },
    { key: "hit", label: t("decision.rules.filterHit"), count: decision.hitCount },
    { key: "pass", label: t("decision.rules.filterPass"), count: decision.passCount },
  ];

  const rows: DecisionRule[] = useMemo(() => {
    if (filter === "hit") {
      return decision.rules.filter((rule) => rule.severity !== "pass");
    }
    if (filter === "pass") {
      return decision.rules.filter((rule) => rule.severity === "pass");
    }
    return decision.rules;
  }, [decision.rules, filter]);

  return (
    <Card
      title={t("decision.rules.title")}
      subtitle={t("decision.rules.subtitle")}
      icon="ri-list-check-2"
      bodyClassName="p-0"
      action={
        <div className="flex items-center gap-1 rounded-full border border-background-200 bg-background-50 p-1">
          {filters.map((item) => {
            const active = item.key === filter;
            return (
              <button
                key={item.key}
                type="button"
                onClick={() => setFilter(item.key)}
                className={`flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-full px-3 py-1 text-[11px] transition-colors ${
                  active
                    ? "bg-primary-500 font-medium text-background-50"
                    : "text-foreground-600 hover:text-foreground-900"
                }`}
              >
                {item.label}
                <span
                  className={`rounded-full px-1.5 font-mono text-[10px] ${
                    active
                      ? "bg-background-50/25 text-background-50"
                      : "bg-background-200/80 text-foreground-600"
                  }`}
                >
                  {item.count}
                </span>
              </button>
            );
          })}
        </div>
      }
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-[920px] border-collapse">
          <thead>
            <tr className="border-b border-background-200/70 text-left">
              <th className="px-4 py-2.5 text-[11px] font-medium text-foreground-500">
                {t("decision.rules.colRule")}
              </th>
              <th className="px-4 py-2.5 text-[11px] font-medium text-foreground-500">
                {t("decision.rules.colResult")}
              </th>
              <th className="px-4 py-2.5 text-[11px] font-medium text-foreground-500">
                {t("decision.rules.colCondition")}
              </th>
              <th className="px-4 py-2.5 text-[11px] font-medium text-foreground-500">
                {t("decision.rules.colActual")}
              </th>
              <th className="px-4 py-2.5 text-[11px] font-medium text-foreground-500">
                {t("decision.rules.colAction")}
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((rule) => {
              const severity = ruleSeverityMeta[rule.severity];
              return (
                <tr
                  key={rule.id}
                  className="border-b border-background-200/50 transition-colors last:border-0 hover:bg-background-50"
                >
                  <td className="max-w-[280px] px-4 py-3 align-top">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[10px] text-foreground-500">
                        {rule.code}
                      </span>
                      <span className="rounded-full bg-secondary-500/12 px-2 py-0.5 text-[10px] text-secondary-300">
                        {isEn ? (rule.categoryEn ?? rule.category) : rule.category}
                      </span>
                    </div>
                    <p className="mt-1 text-[12px] font-medium text-foreground-900">
                      {rule.name}
                    </p>
                    <p className="mt-1 text-[10px] leading-relaxed text-foreground-500">
                      {rule.desc}
                    </p>
                  </td>
                  <td className="px-4 py-3 align-top">
                    <span
                      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-[10px] font-medium ${severity.className}`}
                    >
                      <i className={`${severity.icon} text-[12px]`}></i>
                      {isEn ? severity.labelEn : severity.label}
                    </span>
                  </td>
                  <td className="max-w-[240px] px-4 py-3 align-top">
                    <p className="text-[11px] leading-relaxed text-foreground-600">
                      {rule.condition}
                    </p>
                  </td>
                  <td className="px-4 py-3 align-top">
                    <span className="font-mono text-[11px] text-foreground-800">
                      {rule.actual}
                    </span>
                  </td>
                  <td className="max-w-[220px] px-4 py-3 align-top">
                    <p className="text-[11px] leading-relaxed text-foreground-600">
                      {rule.action}
                    </p>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {rows.length === 0 && (
        <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-full bg-background-200 text-foreground-500">
            <i className="ri-checkbox-circle-line text-xl"></i>
          </span>
          <p className="mt-3 text-[13px] text-foreground-700">
            {t("decision.rules.empty")}
          </p>
        </div>
      )}
    </Card>
  );
}