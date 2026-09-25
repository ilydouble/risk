import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";
import PageFrame from "@/features/workbench-layout/ui/PageFrame";
import StatusPill from "@/entities/risk/ui/StatusPill";
import SearchFilterBar from "@/pages/search/components/SearchFilterBar";
import CompanyResultItem from "@/pages/search/components/CompanyResultItem";
import GroupedResults from "@/pages/search/components/GroupedResults";
import {
  exportCompaniesCsv,
  groupCompanies,
  riskLabel,
  type GroupKey,
  type SortKey,
} from "@/pages/search/lib/query";
import * as CompanyApi from "@/entities/company/api/companyApi";
import { handleApiError } from "@/shared/api/http";
import type { Company, RiskLevel } from "@/entities/demo/model/types";

export default function SearchPage() {
  const { t } = useTranslation();

  const quickTrials = [
    t("search.quickTrial1"),
    t("search.quickTrial2"),
    t("search.quickTrial3"),
    t("search.quickTrial4"),
    t("search.quickTrial5"),
  ];
  const [searchParams, setSearchParams] = useSearchParams();
  const urlQ = searchParams.get("q") ?? "";

  const [keyword, setKeyword] = useState(urlQ);
  const [applied, setApplied] = useState(urlQ);
  const [region, setRegion] = useState("all");
  const [sector, setSector] = useState("all");
  const [risks, setRisks] = useState<RiskLevel[]>([]);
  const [sort, setSort] = useState<SortKey>("score_desc");
  const [view, setView] = useState<"list" | "grouped">("list");
  const [groupKey, setGroupKey] = useState<GroupKey>("region");
  const [toast, setToast] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [results, setResults] = useState<Company[]>([]);
  const [allCompanies, setAllCompanies] = useState<Company[]>([]);
  const [total, setTotal] = useState(0);
  const lastUrlQ = useRef(urlQ);

  useEffect(() => {
    if (urlQ !== lastUrlQ.current) {
      lastUrlQ.current = urlQ;
      setKeyword(urlQ);
      setApplied(urlQ);
    }
  }, [urlQ]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 2600);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    let active = true;
    CompanyApi.requestSearchCompany({ keyword: "", region: "all", sector: "all", risks: [], sort: "score_desc", pagination: { page: 1, pageSize: 100 } })
      .then((data) => { if (active) setAllCompanies(data.items); })
      .catch((failure) => { if (active) setError(handleApiError(failure)); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    CompanyApi.requestSearchCompany({ keyword: applied, region, sector, risks, sort, pagination: { page: 1, pageSize: 100 } })
      .then((data) => {
        if (!active) return;
        setResults(data.items);
        setTotal(data.total);
        setError("");
      })
      .catch((failure) => { if (active) setError(handleApiError(failure)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [applied, region, sector, risks, sort]);

  const groups = useMemo(
    () => (view === "grouped" ? groupCompanies(results, groupKey) : []),
    [results, view, groupKey],
  );

  const riskCounts = useMemo(
    () => ({
      low: results.filter((c) => c.riskLevel === "low").length,
      medium: results.filter((c) => c.riskLevel === "medium").length,
      high: results.filter((c) => c.riskLevel === "high").length,
    }),
    [results],
  );

  const activeCount =
    (applied ? 1 : 0) +
    (region !== "all" ? 1 : 0) +
    (sector !== "all" ? 1 : 0) +
    risks.length;

  const runSearch = (value: string) => {
    const next = value.trim();
    setKeyword(value);
    setApplied(next);
    lastUrlQ.current = next;
    setSearchParams(next ? { q: next } : {}, { replace: true });
  };

  const handleReset = () => {
    setRegion("all");
    setSector("all");
    setRisks([]);
    setSort("score_desc");
  };

  const handleToggleRisk = (risk: RiskLevel) => {
    setRisks((prev) =>
      prev.includes(risk) ? prev.filter((item) => item !== risk) : [...prev, risk],
    );
  };

  const handleDrillDown = (groupValue: string, risk: RiskLevel, label?: string) => {
    if (groupKey === "region") {
      setRegion(groupValue);
    } else {
      setSector(groupValue);
    }
    setRisks([risk]);
    setView("list");
    setToast(
      t("search.toastDrill", {
        value: label ?? groupValue,
        risk: t(riskLabel(risk)),
      }),
    );
  };

  const handleExport = () => {
    if (results.length === 0) return;
    exportCompaniesCsv(results);
    setToast(t("search.toastExport", { count: results.length }));
  };

  return (
    <PageFrame
      title={t("search.title")}
      subtitle={t("search.subtitle")}
      actions={
        <>
          <button
            type="button"
            onClick={() => runSearch("")}
            className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border border-background-300 px-3 py-2 text-xs text-foreground-700 transition-colors hover:border-background-400 hover:text-foreground-950"
          >
            <i className="ri-search-line text-sm"></i>
            {t("search.browseAll")}
          </button>
          <button
            type="button"
            onClick={handleExport}
            disabled={results.length === 0}
            className={`flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md px-3.5 py-2 text-xs font-medium transition-colors ${
              results.length === 0
                ? "cursor-not-allowed bg-background-200 text-foreground-500/60"
                : "bg-primary-500 text-background-50 hover:bg-primary-600"
            }`}
          >
            <i className="ri-download-2-line text-sm"></i>
            {t("search.exportResults")}
          </button>
        </>
      }
      headerExtra={
        <div className="mb-4 space-y-3">
          <div className="rounded-lg border border-background-200 bg-background-100 p-3">
            <div className="flex flex-col gap-2 sm:flex-row">
              <div className="flex flex-1 items-center gap-2 rounded-md border border-background-200 bg-background-50 px-3 py-2.5 transition-colors focus-within:border-primary-400">
                <span className="flex h-5 w-5 items-center justify-center text-foreground-500">
                  <i className="ri-search-2-line text-base"></i>
                </span>
                <input
                  value={keyword}
                  onChange={(event) => setKeyword(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") runSearch(keyword);
                  }}
                  placeholder={t("search.searchPlaceholder")}
                  className="w-full bg-transparent text-sm text-foreground-900 placeholder:text-foreground-500 focus:outline-none"
                />
                {keyword && (
                  <button
                    type="button"
                    onClick={() => runSearch("")}
                    className="flex h-5 w-5 cursor-pointer items-center justify-center rounded-full text-foreground-500 transition-colors hover:text-foreground-900"
                    aria-label={t("search.clearKeyword")}
                  >
                    <i className="ri-close-circle-line text-base"></i>
                  </button>
                )}
              </div>
              <button
                type="button"
                onClick={() => runSearch(keyword)}
                className="flex cursor-pointer items-center justify-center gap-1.5 whitespace-nowrap rounded-md bg-primary-500 px-5 py-2.5 text-sm font-medium text-background-50 transition-colors hover:bg-primary-600"
              >
                <i className="ri-search-line text-base"></i>
                {t("search.searchBtn")}
              </button>
            </div>

            <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
              <span className="text-[11px] text-foreground-500">
                {t("search.quickTrials")}
              </span>
              {quickTrials.map((trial) => (
                <button
                  key={trial}
                  type="button"
                  onClick={() => runSearch(trial)}
                  className="cursor-pointer whitespace-nowrap rounded-full border border-background-200 px-2.5 py-1 font-mono text-[11px] text-foreground-600 transition-colors hover:border-primary-400 hover:text-primary-400"
                >
                  {trial}
                </button>
              ))}
            </div>
          </div>

          <SearchFilterBar
            companies={allCompanies}
            region={region}
            onRegionChange={setRegion}
            sector={sector}
            onSectorChange={setSector}
            risks={risks}
            onToggleRisk={handleToggleRisk}
            sort={sort}
            onSortChange={setSort}
            activeCount={activeCount}
            onReset={handleReset}
          />
        </div>
      }
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <p className="text-sm text-foreground-800">
            {t("search.hitPrefix")}{" "}
            <span className="font-mono text-base font-semibold text-primary-400">
              {total}
            </span>{" "}
            {t("search.hitSuffix")}
            <span className="ml-1 text-xs text-foreground-500">
              {t("search.inLibrary", { count: allCompanies.length })}
            </span>
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill
              level="low"
              label={`${t("risk.low")} ${riskCounts.low}`}
              size="sm"
            />
            <StatusPill
              level="medium"
              label={`${t("risk.medium")} ${riskCounts.medium}`}
              size="sm"
            />
            <StatusPill
              level="high"
              label={`${t("risk.high")} ${riskCounts.high}`}
              size="sm"
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1 rounded-full border border-background-200 bg-background-100 p-1">
            <button
              type="button"
              onClick={() => setView("list")}
              className={`flex cursor-pointer items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-1 text-[11px] transition-colors ${
                view === "list"
                  ? "bg-primary-500 text-background-50"
                  : "text-foreground-500 hover:text-foreground-800"
              }`}
            >
              <i className="ri-list-check-2 text-[13px]"></i>
              {t("search.listView")}
            </button>
            <button
              type="button"
              onClick={() => setView("grouped")}
              className={`flex cursor-pointer items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-1 text-[11px] transition-colors ${
                view === "grouped"
                  ? "bg-primary-500 text-background-50"
                  : "text-foreground-500 hover:text-foreground-800"
              }`}
            >
              <i className="ri-group-2-line text-[13px]"></i>
              {t("search.groupView")}
            </button>
          </div>

          {view === "grouped" && (
            <div className="flex items-center gap-1 rounded-full border border-background-200 bg-background-100 p-1">
              <button
                type="button"
                onClick={() => setGroupKey("region")}
                className={`flex cursor-pointer items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-1 text-[11px] transition-colors ${
                  groupKey === "region"
                    ? "bg-secondary-500 text-background-50"
                    : "text-foreground-500 hover:text-foreground-800"
                }`}
              >
                <i className="ri-earth-line text-[13px]"></i>
                {t("search.byRegion")}
              </button>
              <button
                type="button"
                onClick={() => setGroupKey("sector")}
                className={`flex cursor-pointer items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-1 text-[11px] transition-colors ${
                  groupKey === "sector"
                    ? "bg-secondary-500 text-background-50"
                    : "text-foreground-500 hover:text-foreground-800"
                }`}
              >
                <i className="ri-stack-line text-[13px]"></i>
                {t("search.bySector")}
              </button>
            </div>
          )}

          {applied && (
          <span className="flex items-center gap-1.5 rounded-full border border-primary-400/40 bg-primary-500/10 px-2.5 py-1 text-[11px] text-primary-400">
            <i className="ri-filter-3-line text-[13px]"></i>
            {t("search.keywordChip", { keyword: applied })}
            <button
              type="button"
              onClick={() => runSearch("")}
              className="flex cursor-pointer items-center text-primary-400 transition-colors hover:text-primary-300"
              aria-label={t("search.removeKeyword")}
            >
              <i className="ri-close-line text-[13px]"></i>
            </button>
          </span>
          )}
        </div>
      </div>

      {error && <p role="alert" className="mb-3 text-xs text-accent-400">{error}</p>}
      {loading && <p className="mb-3 text-xs text-foreground-500">{t("search.searchBtn")}…</p>}
      {results.length > 0 ? (
        view === "grouped" ? (
          <GroupedResults
            groups={groups}
            keyword={applied}
            groupKey={groupKey}
            onDrillDown={handleDrillDown}
          />
        ) : (
          <div className="animate-fade-in space-y-2.5">
            {results.map((company, index) => (
              <div
                key={company.id}
                className="animate-fade-up"
                style={{ animationDelay: `${Math.min(index, 8) * 40}ms` }}
              >
                <CompanyResultItem company={company} keyword={applied} />
              </div>
            ))}
          </div>
        )
      ) : (
        <div className="animate-fade-in flex flex-col items-center justify-center rounded-lg border border-dashed border-background-300 bg-background-100 px-6 py-20 text-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-full bg-background-200 text-foreground-500">
            <i className="ri-search-eye-line text-2xl"></i>
          </span>
          <h3 className="mt-4 text-[15px] font-semibold text-foreground-950">
            {t("search.emptyTitle")}
          </h3>
          <p className="mt-1.5 max-w-md text-sm text-foreground-500">
            {t("search.emptyDescPrefix")}
            {risks.length > 0 &&
              `「${risks.map((r) => t(riskLabel(r))).join("、")}」`}
            {t("search.emptyDescSuffix")}
          </p>
          <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
            <button
              type="button"
              onClick={handleReset}
              className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border border-background-300 px-3.5 py-2 text-xs text-foreground-700 transition-colors hover:border-primary-400 hover:text-primary-400"
            >
              <i className="ri-refresh-line text-sm"></i>
              {t("search.resetFilters")}
            </button>
            <button
              type="button"
              onClick={() => runSearch("")}
              className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md bg-primary-500 px-3.5 py-2 text-xs font-medium text-background-50 transition-colors hover:bg-primary-600"
            >
              <i className="ri-list-check-3 text-sm"></i>
              {t("search.browseAllCompanies")}
            </button>
          </div>
        </div>
      )}

      {toast && (
        <div className="animate-fade-in fixed bottom-6 left-1/2 z-40 -translate-x-1/2 rounded-md border border-background-300 bg-background-100 px-4 py-2.5 text-xs text-foreground-900">
          <span className="flex items-center gap-2">
            <i className="ri-checkbox-circle-line text-base text-primary-400"></i>
            {toast}
          </span>
        </div>
      )}
    </PageFrame>
  );
}
