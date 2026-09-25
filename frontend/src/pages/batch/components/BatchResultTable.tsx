import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import RiskBadge from "@/components/base/RiskBadge";
import { useLang } from "@/hooks/useLang";
import { getStatusMeta } from "@/pages/batch/lib/batch";
import type { BatchRow, BatchRowStatus, RiskLevel } from "@/types";

interface BatchResultTableProps {
  rows: BatchRow[];
}

type SortKey = "rank" | "score" | "pd";
type RiskFilter = "all" | RiskLevel;
type StatusFilter = "all" | BatchRowStatus;

export default function BatchResultTable({ rows }: BatchResultTableProps) {
  const { t } = useTranslation();
  const { lang, pick } = useLang();
  const [sortKey, setSortKey] = useState<SortKey>("rank");
  const [sortAsc, setSortAsc] = useState(true);
  const [risk, setRisk] = useState<RiskFilter>("all");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [query, setQuery] = useState("");

  const statusMeta = useMemo(() => getStatusMeta(lang), [lang]);

  const RISK_FILTERS: { value: RiskFilter; label: string }[] = [
    { value: "all", label: t("batch.table.riskAll") },
    { value: "low", label: t("risk.low") },
    { value: "medium", label: t("risk.medium") },
    { value: "high", label: t("risk.high") },
  ];

  const STATUS_FILTERS: { value: StatusFilter; label: string }[] = [
    { value: "all", label: t("batch.table.statusAll") },
    { value: "ok", label: t("batch.status.ok") },
    { value: "review", label: t("batch.status.review") },
    { value: "unmatched", label: t("batch.status.unmatched") },
  ];

  const COLUMNS: { key: SortKey | null; label: string; align: string }[] = [
    { key: "rank", label: t("batch.table.col.rank"), align: "text-center" },
    { key: null, label: t("batch.table.col.name"), align: "text-left" },
    { key: null, label: t("batch.table.col.country"), align: "text-left" },
    { key: null, label: t("batch.table.col.industry"), align: "text-left" },
    { key: "score", label: t("batch.table.col.score"), align: "text-right" },
    { key: null, label: t("batch.table.col.grade"), align: "text-center" },
    { key: null, label: t("batch.table.col.risk"), align: "text-left" },
    { key: "pd", label: t("batch.table.col.pd"), align: "text-right" },
    { key: null, label: t("batch.table.col.limit"), align: "text-right" },
    { key: null, label: t("batch.table.col.status"), align: "text-left" },
    { key: null, label: t("batch.table.col.profile"), align: "text-center" },
  ];

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = rows.filter((row) => {
      if (risk !== "all") {
        if (!row.matched || row.riskLevel !== risk) return false;
      }
      if (status !== "all" && row.status !== status) return false;
      if (q) {
        const haystack = `${row.nameCn} ${row.nameEn} ${row.rawName} ${row.country} ${row.countryEn ?? ""} ${row.industry} ${row.industryEn ?? ""}`.toLowerCase();
        if (!haystack.includes(q)) return false;
      }
      return true;
    });

    list.sort((a, b) => {
      if (sortKey === "rank") {
        const av = a.rank ?? Number.POSITIVE_INFINITY;
        const bv = b.rank ?? Number.POSITIVE_INFINITY;
        return sortAsc ? av - bv : bv - av;
      }
      if (sortKey === "score") {
        const av = a.matched ? a.creditScore : -1;
        const bv = b.matched ? b.creditScore : -1;
        return sortAsc ? av - bv : bv - av;
      }
      const av = a.matched ? a.defaultProb : -1;
      const bv = b.matched ? b.defaultProb : -1;
      return sortAsc ? av - bv : bv - av;
    });

    return list;
  }, [rows, risk, status, query, sortKey, sortAsc]);

  const toggleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortAsc((prev) => !prev);
    } else {
      setSortKey(key);
      setSortAsc(key === "rank");
    }
  };

  return (
    <section className="animate-fade-up rounded-lg border border-background-200 bg-background-100">
      <header className="flex flex-col gap-3 border-b border-background-200/70 px-4 py-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-2.5">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-secondary-500/14 text-secondary-400">
            <i className="ri-sort-desc text-[15px]"></i>
          </span>
          <div>
            <h3 className="text-[15px] font-semibold leading-tight text-foreground-950">
              {t("batch.table.title")}
            </h3>
            <p className="mt-0.5 text-xs text-foreground-500">
              {t("batch.table.countNote", {
                total: rows.length,
                filtered: filtered.length,
              })}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <span className="pointer-events-none absolute left-2.5 top-1/2 flex h-4 w-4 -translate-y-1/2 items-center justify-center text-foreground-500">
              <i className="ri-search-line text-[15px]"></i>
            </span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t("batch.table.searchPlaceholder")}
              className="w-full rounded-md border border-background-200 bg-background-50 py-2 pl-8 pr-3 text-xs text-foreground-900 outline-none transition-colors placeholder:text-foreground-500 focus:border-primary-400 sm:w-56"
            />
          </div>
          <div className="flex items-center gap-1 rounded-full border border-background-200 bg-background-50 px-1 py-1">
            {RISK_FILTERS.map((item) => (
              <button
                key={item.value}
                type="button"
                onClick={() => setRisk(item.value)}
                className={`cursor-pointer whitespace-nowrap rounded-full px-2.5 py-1 text-[11px] transition-colors ${
                  risk === item.value
                    ? "bg-primary-500/14 text-primary-400"
                    : "text-foreground-600 hover:text-foreground-950"
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-1 rounded-full border border-background-200 bg-background-50 px-1 py-1">
            {STATUS_FILTERS.map((item) => (
              <button
                key={item.value}
                type="button"
                onClick={() => setStatus(item.value)}
                className={`cursor-pointer whitespace-nowrap rounded-full px-2.5 py-1 text-[11px] transition-colors ${
                  status === item.value
                    ? "bg-secondary-500/16 text-secondary-400"
                    : "text-foreground-600 hover:text-foreground-950"
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
      </header>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[960px] border-collapse">
          <thead>
            <tr className="border-b border-background-200/70">
              {COLUMNS.map((column) => {
                const active = column.key !== null && column.key === sortKey;
                return (
                  <th
                    key={column.label}
                    className={`whitespace-nowrap px-3 py-2.5 text-[11px] font-medium text-foreground-500 ${column.align}`}
                  >
                    {column.key ? (
                      <button
                        type="button"
                        onClick={() => toggleSort(column.key as SortKey)}
                        className={`inline-flex cursor-pointer items-center gap-1 transition-colors hover:text-foreground-950 ${
                          active ? "text-primary-400" : ""
                        }`}
                      >
                        {column.label}
                        <i
                          className={`text-[12px] ${
                            active
                              ? sortAsc
                                ? "ri-arrow-up-line"
                                : "ri-arrow-down-line"
                              : "ri-arrow-up-down-line"
                          }`}
                        ></i>
                      </button>
                    ) : (
                      column.label
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {filtered.map((row) => {
              const meta = statusMeta[row.status];
              return (
                <tr
                  key={row.id}
                  className="border-b border-background-200/50 transition-colors last:border-0 hover:bg-background-200/40"
                >
                  <td className="px-3 py-2.5 text-center">
                    {row.rank ? (
                      <span
                        className={`inline-flex h-6 min-w-6 items-center justify-center rounded-full px-1.5 font-mono text-[11px] ${
                          row.rank <= 3
                            ? "bg-primary-500/14 text-primary-400"
                            : "bg-background-200/70 text-foreground-600"
                        }`}
                      >
                        {row.rank}
                      </span>
                    ) : (
                      <span className="font-mono text-[11px] text-foreground-500">
                        —
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2.5">
                    <p className="max-w-[220px] truncate text-[12px] font-medium text-foreground-950">
                      {row.nameCn}
                    </p>
                    <p className="max-w-[220px] truncate text-[10px] text-foreground-500">
                      {row.nameEn}
                    </p>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-[11px] text-foreground-700">
                    {pick(row.country, row.countryEn)}
                  </td>
                  <td className="px-3 py-2.5 text-[11px] text-foreground-600">
                    <span className="block max-w-[160px] truncate">
                      {pick(row.industry, row.industryEn)}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-[12px] font-semibold text-foreground-950">
                    {row.matched ? row.creditScore : "—"}
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    <span className="inline-flex items-center rounded bg-background-200/70 px-1.5 py-0.5 font-mono text-[10px] text-foreground-700">
                      {row.grade}
                    </span>
                  </td>
                  <td className="px-3 py-2.5">
                    {row.matched ? (
                      <RiskBadge level={row.riskLevel} size="sm" />
                    ) : (
                      <span className="text-[11px] text-foreground-500">—</span>
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-[11px] text-foreground-700">
                    {row.matched ? `${row.defaultProb.toFixed(1)}%` : "—"}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-right font-mono text-[11px] text-foreground-700">
                    {row.creditLimit}
                  </td>
                  <td className="px-3 py-2.5">
                    <div className="flex flex-col gap-1">
                      <span
                        className={`inline-flex w-fit items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-[10px] font-medium ${meta.className}`}
                      >
                        <i className={`${meta.icon} text-[11px]`}></i>
                        {meta.label}
                      </span>
                      {row.issues.length > 0 && (
                        <span
                          className="max-w-[200px] truncate text-[10px] text-foreground-500"
                          title={row.issues.join("；")}
                        >
                          {row.issues[0]}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    {row.companyId ? (
                      <Link
                        to={`/company/${row.companyId}`}
                        className="inline-flex h-7 w-7 cursor-pointer items-center justify-center rounded-md border border-background-300 text-foreground-600 transition-colors hover:border-primary-400 hover:text-primary-400"
                        title={t("batch.table.viewProfile")}
                      >
                        <i className="ri-arrow-right-up-line text-[14px]"></i>
                      </Link>
                    ) : (
                      <span className="inline-flex h-7 w-7 items-center justify-center text-foreground-500 opacity-40">
                        <i className="ri-subtract-line text-[14px]"></i>
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {filtered.length === 0 && (
          <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-background-200 text-foreground-500">
              <i className="ri-filter-off-line text-xl"></i>
            </span>
            <p className="mt-3 text-[13px] font-medium text-foreground-900">
              {t("batch.table.emptyTitle")}
            </p>
            <p className="mt-1 text-xs text-foreground-500">
              {t("batch.table.emptyDesc")}
            </p>
          </div>
        )}
      </div>
    </section>
  );
}