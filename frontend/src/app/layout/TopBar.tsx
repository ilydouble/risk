import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import * as CompanyApi from "@/entities/company/api/companyApi";
import * as AuthApi from "@/features/auth/api/authApi";
import { useAuthUser } from "@/features/auth/model/AuthContext";
import { handleApiError } from "@/shared/api/http";
import type { Company } from "@/entities/demo/model/types";
import { presetCases } from "@/features/demo-scenarios/model/fixtures/overview";
import { useDemoMode } from "@/features/demo-scenarios/model/DemoModeContext";
import RiskBadge from "@/entities/risk/ui/RiskBadge";
import StatusDot from "@/entities/risk/ui/StatusDot";
import CompanyBreadcrumb from "@/app/layout/CompanyBreadcrumb";
import LanguageSwitcher from "@/shared/ui/LanguageSwitcher";
import { useLang } from "@/shared/lib/useLang";

export default function TopBar({ onMenuClick }: { onMenuClick: () => void }) {
  const { t } = useTranslation();
  const { pick } = useLang();
  const authUser = useAuthUser();
  const displayName = authUser?.displayName ?? authUser?.username ?? "";
  const navigate = useNavigate();
  const { demoMode, initialized, initialize, toggleDemoMode } = useDemoMode();
  const [query, setQuery] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [caseOpen, setCaseOpen] = useState(false);
  const [results, setResults] = useState<Company[]>([]);
  const searchRef = useRef<HTMLDivElement>(null);
  const caseRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!query.trim()) { setResults([]); return; }
    let active = true;
    const timer = window.setTimeout(() => {
      CompanyApi.requestSearchCompany({ keyword: query.trim(), region: "all", sector: "all", risks: [], sort: "score_desc", pagination: { page: 1, pageSize: 6 } })
        .then((data) => { if (active) setResults(data.items); })
        .catch((failure) => { if (active) handleApiError(failure); });
    }, 180);
    return () => { active = false; window.clearTimeout(timer); };
  }, [query]);

  useEffect(() => {
    const handler = (event: MouseEvent) => {
      const target = event.target as Node;
      if (searchRef.current && !searchRef.current.contains(target)) {
        setSearchOpen(false);
      }
      if (caseRef.current && !caseRef.current.contains(target)) {
        setCaseOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const submitSearch = () => {
    const q = query.trim();
    navigate(q ? `/search?q=${encodeURIComponent(q)}` : "/search");
    setSearchOpen(false);
  };

  const handleInitialize = () => {
    initialize();
    setCaseOpen((prev) => !prev);
  };

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-background-200 bg-background-50/95 px-4 backdrop-blur md:px-6">
      <button
        type="button"
        onClick={onMenuClick}
        className="flex h-9 w-9 cursor-pointer items-center justify-center rounded-md border border-background-200 text-foreground-700 hover:bg-background-200 lg:hidden"
        aria-label={t("topbar.openNav")}
      >
        <i className="ri-menu-line text-lg"></i>
      </button>

      <CompanyBreadcrumb />

      <div ref={searchRef} className="relative w-full min-w-0 max-w-md">
        <div className="flex items-center gap-2 rounded-md border border-background-200 bg-background-100 px-3 py-2 transition-colors focus-within:border-primary-400">
          <span className="flex h-4 w-4 items-center justify-center text-foreground-500">
            <i className="ri-search-line text-base"></i>
          </span>
          <input
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSearchOpen(true);
            }}
            onFocus={() => setSearchOpen(true)}
            onKeyDown={(e) => {
              if (e.key === "Enter") submitSearch();
            }}
            placeholder={t("topbar.searchPlaceholder")}
            className="w-full bg-transparent text-sm text-foreground-900 placeholder:text-foreground-500 focus:outline-none"
          />
          <kbd className="hidden rounded border border-background-300 px-1.5 py-0.5 font-mono text-[10px] text-foreground-500 sm:inline-block">
            Enter
          </kbd>
        </div>

        {searchOpen && results.length > 0 && (
          <div className="animate-fade-in absolute left-0 right-0 top-full z-30 mt-2 overflow-hidden rounded-md border border-background-200 bg-background-100 shadow-none">
            <ul>
              {results.map((c) => (
                <li key={c.id}>
                  <button
                    type="button"
                    onMouseDown={() => {
                      navigate(`/company/${c.id}`);
                      setQuery("");
                      setSearchOpen(false);
                    }}
                    className="flex w-full cursor-pointer items-center gap-3 px-3 py-2.5 text-left transition-colors hover:bg-background-200/70"
                  >
                    <span className="flex h-8 w-8 items-center justify-center rounded-md bg-background-200 text-foreground-600">
                      <i className="ri-building-2-line text-[15px]"></i>
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm text-foreground-900">
                        {pick(c.nameCn, c.nameEn)}
                      </span>
                      <span className="block truncate font-mono text-[11px] text-foreground-500">
                        {c.regNo} · {c.country}
                      </span>
                    </span>
                    <RiskBadge level={c.riskLevel} size="sm" />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="ml-auto flex items-center gap-2 md:gap-3">
        <div ref={caseRef} className="relative">
          <button
            type="button"
            onClick={handleInitialize}
            className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border border-primary-400/40 bg-primary-500/12 px-3 py-2 text-xs font-medium text-primary-400 transition-colors hover:bg-primary-500/20"
          >
            <i className="ri-flashlight-line text-sm"></i>
            <span className="hidden sm:inline">
              {initialized ? t("topbar.presetCases") : t("topbar.init")}
            </span>
          </button>

          {caseOpen && (
            <div className="animate-fade-in absolute right-0 top-full z-30 mt-2 w-80 overflow-hidden rounded-md border border-background-200 bg-background-100">
              <div className="border-b border-background-200 px-3 py-2">
                <p className="text-xs font-medium text-foreground-900">
                  {t("topbar.presetTitle")}
                </p>
                <p className="mt-0.5 text-[11px] text-foreground-500">
                  {t("topbar.presetHint")}
                </p>
              </div>
              <ul className="max-h-80 overflow-y-auto">
                {presetCases.map((c) => (
                  <li key={c.id}>
                    <button
                      type="button"
                      onClick={() => {
                        navigate(`/company/${c.companyId}`);
                        setCaseOpen(false);
                      }}
                      className="w-full cursor-pointer border-b border-background-200/60 px-3 py-2.5 text-left transition-colors last:border-b-0 hover:bg-background-200/70"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[13px] font-medium text-foreground-900">
                          {t(`overview.preset.${c.id.replace("-", "")}.title`)}
                        </span>
                        <RiskBadge level={c.riskLevel} size="sm" />
                      </div>
                      <p className="mt-1 text-[11px] leading-relaxed text-foreground-500">
                        {t(`overview.preset.${c.id.replace("-", "")}.summary`)}
                      </p>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <button
          type="button"
          onClick={toggleDemoMode}
          className="flex cursor-pointer items-center gap-2 rounded-md border border-background-200 bg-background-100 px-2.5 py-2 transition-colors hover:border-background-300"
          aria-label={t("topbar.toggleDemo")}
        >
          <span
            className={`relative h-4 w-8 rounded-full transition-colors ${
              demoMode ? "bg-primary-500" : "bg-background-300"
            }`}
          >
            <span
              className={`absolute top-0.5 h-3 w-3 rounded-full bg-background-50 transition-transform ${
                demoMode ? "translate-x-4" : "translate-x-0.5"
              }`}
            ></span>
          </span>
          <span className="hidden whitespace-nowrap text-xs text-foreground-600 lg:inline">
            {t("topbar.demoMode")}
          </span>
        </button>

        <button
          type="button"
          className="relative flex h-9 w-9 cursor-pointer items-center justify-center rounded-md border border-background-200 bg-background-100 text-foreground-600 hover:border-background-300"
          aria-label={t("topbar.notifications")}
        >
          <i className="ri-notification-3-line text-[17px]"></i>
          <StatusDot level="high" size="xs" className="absolute right-2 top-2" />
        </button>

        <LanguageSwitcher />

        <button type="button" onClick={() => AuthApi.requestLogout({}).then(() => navigate("/login", { replace: true })).catch((failure) => handleApiError(failure))} className="flex h-9 w-9 items-center justify-center rounded-md border border-background-200 text-foreground-600 hover:border-primary-400" aria-label={`${displayName} · ${t("common.logout")}`}><i className="ri-logout-box-r-line" /></button>

        <div className="flex h-9 items-center gap-2 rounded-md border border-background-200 bg-background-100 pl-1 pr-3">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-secondary-500/20 text-secondary-300">
            <i className="ri-user-3-line text-[15px]"></i>
          </span>
          <span className="hidden leading-tight sm:block">
            <span className="block text-xs font-medium text-foreground-900">
              {displayName}
            </span>
            <span className="block text-[10px] text-foreground-500">
              {t("topbar.demoEnvironment")}
            </span>
          </span>
        </div>
      </div>
    </header>
  );
}
