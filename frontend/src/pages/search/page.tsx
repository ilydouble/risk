import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";
import * as OverviewApi from "@/entities/overview/api/overviewApi";
import PageFrame from "@/features/workbench-layout/ui/PageFrame";
import SampleResultItem from "@/pages/search/components/SampleResultItem";
import {
  exportOverviewSamplesCsv,
  type OverviewSampleCompany,
  type SearchCategory,
  type SearchSort,
} from "@/pages/search/lib/sampleQuery";
import { handleApiError } from "@/shared/api/http";
import SelectMenu from "@/shared/ui/SelectMenu";

const PAGE_SIZE = 30;

export default function SearchPage() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const urlQuery = searchParams.get("q") ?? "";
  const [keyword, setKeyword] = useState(urlQuery);
  const [applied, setApplied] = useState(urlQuery);
  const [category, setCategory] = useState<SearchCategory>("all");
  const [industryCode, setIndustryCode] = useState("all");
  const [sort, setSort] = useState<SearchSort>("name_asc");
  const [page, setPage] = useState(1);
  const [results, setResults] = useState<OverviewSampleCompany[]>([]);
  const [industryCodes, setIndustryCodes] = useState<string[]>([]);
  const [sampleCount, setSampleCount] = useState(0);
  const [datasetName, setDatasetName] = useState("");
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const lastUrlQuery = useRef(urlQuery);

  const quickTrials = ["Liquidation", "Struck Off", "Live", "PTE. LTD."];

  useEffect(() => {
    if (urlQuery !== lastUrlQuery.current) {
      lastUrlQuery.current = urlQuery;
      setKeyword(urlQuery);
      setApplied(urlQuery);
      setPage(1);
    }
  }, [urlQuery]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 2600);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    OverviewApi.requestSearchOverviewCompany({
      keyword: applied,
      category,
      industryCode,
      sort,
      pagination: { page, pageSize: PAGE_SIZE },
    })
      .then((data) => {
        if (!active) return;
        setResults(data.items);
        setTotal(data.total);
        setIndustryCodes(data.industryCodes);
        setSampleCount(data.sampling.sampleCount);
        setDatasetName(data.dataset.name);
        setError("");
      })
      .catch((failure) => {
        if (active) setError(handleApiError(failure));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [applied, category, industryCode, page, sort]);

  const runSearch = (value: string) => {
    const next = value.trim();
    setKeyword(value);
    setApplied(next);
    setPage(1);
    lastUrlQuery.current = next;
    setSearchParams(next ? { q: next } : {}, { replace: true });
  };

  const resetFilters = () => {
    setCategory("all");
    setIndustryCode("all");
    setSort("name_asc");
    runSearch("");
  };

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const activeCount = (applied ? 1 : 0) + (category !== "all" ? 1 : 0) + (industryCode !== "all" ? 1 : 0);

  return (
    <PageFrame
      title={t("search.title")}
      subtitle={t("search.subtitle")}
      dataset
      actions={
        <>
          <button type="button" onClick={resetFilters} className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border border-background-300 px-3 py-2 text-xs text-foreground-700 transition-colors hover:border-background-400 hover:text-foreground-950">
            <i className="ri-search-line text-sm" />
            {t("search.browseAll")}
          </button>
          <button type="button" onClick={() => { exportOverviewSamplesCsv(results); setToast(t("search.toastExport", { count: results.length })); }} disabled={results.length === 0} className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md bg-primary-500 px-3.5 py-2 text-xs font-medium text-background-50 transition-colors hover:bg-primary-600 disabled:cursor-not-allowed disabled:bg-background-200 disabled:text-foreground-500/60">
            <i className="ri-download-2-line text-sm" />
            {t("search.exportPage")}
          </button>
        </>
      }
      headerExtra={
        <div className="mb-4 space-y-3">
          <div className="rounded-lg border border-accent-500/25 bg-accent-500/8 px-4 py-3 text-xs text-foreground-700">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-accent-500/15 px-2 py-1 font-semibold text-accent-400">{t("search.realDataset")}</span>
              <span>{datasetName || t("search.datasetLoading")}</span>
            </div>
            <p className="mt-1.5 text-foreground-500">{t("search.sampleBoundary", { count: sampleCount || 300 })}</p>
          </div>

          <div className="rounded-lg border border-background-200 bg-background-100 p-3">
            <div className="flex flex-col gap-2 sm:flex-row">
              <div className="flex flex-1 items-center gap-2 rounded-md border border-background-200 bg-background-50 px-3 py-2.5 focus-within:border-primary-400">
                <i className="ri-search-2-line text-base text-foreground-500" />
                <input value={keyword} onChange={(event) => setKeyword(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") runSearch(keyword); }} placeholder={t("search.searchPlaceholder")} className="w-full bg-transparent text-sm text-foreground-900 placeholder:text-foreground-500 focus:outline-none" />
                {keyword && <button type="button" onClick={() => runSearch("")} aria-label={t("search.clearKeyword")} className="text-foreground-500 hover:text-foreground-900"><i className="ri-close-circle-line text-base" /></button>}
              </div>
              <button type="button" onClick={() => runSearch(keyword)} className="flex cursor-pointer items-center justify-center gap-1.5 rounded-md bg-primary-500 px-5 py-2.5 text-sm font-medium text-background-50 hover:bg-primary-600">
                <i className="ri-search-line text-base" />
                {t("search.searchBtn")}
              </button>
            </div>
            <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
              <span className="text-[11px] text-foreground-500">{t("search.quickTrials")}</span>
              {quickTrials.map((trial) => <button key={trial} type="button" onClick={() => runSearch(trial)} className="rounded-full border border-background-200 px-2.5 py-1 font-mono text-[11px] text-foreground-600 hover:border-primary-400 hover:text-primary-400">{trial}</button>)}
            </div>
          </div>

          <div className="flex flex-col gap-3 rounded-lg border border-background-200 bg-background-100 p-3 lg:flex-row lg:items-center">
            <SelectMenu label={t("search.filterCategory")} icon="ri-price-tag-3-line" value={category} options={(["all", "healthy", "distress", "unlabeled"] as const).map((value) => ({ value, label: t(`search.category.${value}`) }))} onChange={(value) => { setCategory(value as SearchCategory); setPage(1); }} className="w-full sm:w-44" />
            <SelectMenu label="SSIC" icon="ri-stack-line" value={industryCode} options={[{ value: "all", label: t("search.allIndustries") }, ...industryCodes.map((value) => ({ value, label: value }))]} onChange={(value) => { setIndustryCode(value); setPage(1); }} className="w-full sm:w-44" />
            <SelectMenu label={t("search.filterSort")} icon="ri-sort-desc" value={sort} options={(["name_asc", "age_desc", "relations_desc"] as const).map((value) => ({ value, label: t(`search.sort.${value}`) }))} onChange={(value) => { setSort(value as SearchSort); setPage(1); }} className="w-full sm:w-56" />
            <button type="button" onClick={resetFilters} disabled={activeCount === 0} className="flex cursor-pointer items-center gap-1.5 rounded-md border border-background-300 px-3 py-2 text-xs text-foreground-700 hover:border-primary-400 disabled:cursor-not-allowed disabled:opacity-40">
              <i className="ri-refresh-line text-sm" />
              {t("search.resetFilterBtn")}
            </button>
          </div>
        </div>
      }
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-foreground-800">
          {t("search.hitPrefix")} <span className="font-mono text-base font-semibold text-primary-400">{total}</span> {t("search.hitSuffix")}
          <span className="ml-1 text-xs text-foreground-500">{t("search.inSample", { count: sampleCount || 300 })}</span>
        </p>
        <span className="text-xs text-foreground-500">{t("search.page", { current: page, total: totalPages })}</span>
      </div>

      {error && <p role="alert" className="mb-3 rounded-md border border-danger-500/25 bg-danger-500/8 p-3 text-xs text-danger-500">{error}</p>}
      {loading && <p role="status" className="mb-3 text-xs text-foreground-500">{t("search.loading")}</p>}

      {!loading && results.length > 0 && (
        <div className="animate-fade-in space-y-2.5">
          {results.map((company, index) => <div key={company.companyId} className="animate-fade-up" style={{ animationDelay: `${Math.min(index, 8) * 35}ms` }}><SampleResultItem company={company} keyword={applied} /></div>)}
        </div>
      )}

      {!loading && results.length === 0 && !error && (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-background-300 bg-background-100 px-6 py-20 text-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-full bg-background-200 text-foreground-500"><i className="ri-search-eye-line text-2xl" /></span>
          <h3 className="mt-4 text-[15px] font-semibold text-foreground-950">{t("search.emptyTitle")}</h3>
          <p className="mt-1.5 max-w-md text-sm text-foreground-500">{t("search.emptyDesc")}</p>
          <button type="button" onClick={resetFilters} className="mt-5 rounded-md border border-background-300 px-3.5 py-2 text-xs text-foreground-700 hover:border-primary-400 hover:text-primary-400">{t("search.browseAllCompanies")}</button>
        </div>
      )}

      {totalPages > 1 && (
        <div className="mt-4 flex items-center justify-center gap-3">
          <button type="button" disabled={page === 1} onClick={() => setPage((value) => Math.max(1, value - 1))} className="rounded-md border border-background-300 px-3 py-2 text-xs text-foreground-700 disabled:cursor-not-allowed disabled:opacity-40">{t("search.previous")}</button>
          <span className="font-mono text-xs text-foreground-500">{page} / {totalPages}</span>
          <button type="button" disabled={page === totalPages} onClick={() => setPage((value) => Math.min(totalPages, value + 1))} className="rounded-md border border-background-300 px-3 py-2 text-xs text-foreground-700 disabled:cursor-not-allowed disabled:opacity-40">{t("search.next")}</button>
        </div>
      )}

      {toast && <div className="animate-fade-in fixed bottom-6 left-1/2 z-40 -translate-x-1/2 rounded-md border border-background-300 bg-background-100 px-4 py-2.5 text-xs text-foreground-900"><i className="ri-checkbox-circle-line mr-2 text-primary-400" />{toast}</div>}
    </PageFrame>
  );
}
