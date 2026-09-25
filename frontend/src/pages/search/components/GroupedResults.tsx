import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { useLang } from "@/shared/lib/useLang";
import RiskBadge from "@/entities/risk/ui/RiskBadge";
import StatusPill from "@/entities/risk/ui/StatusPill";
import Tooltip from "@/shared/ui/Tooltip";
import { RISK_HINT } from "@/entities/risk/model/status";
import Highlight from "@/pages/search/components/Highlight";
import type { Company, RiskLevel } from "@/entities/demo/model/types";
import type { CompanyGroup, GroupKey } from "@/pages/search/lib/query";

const RISK_SEGMENTS: { key: RiskLevel; label: string; bg: string }[] = [
  { key: "low", label: "search.riskShortLow", bg: "risk-bg-low" },
  { key: "medium", label: "search.riskShortMedium", bg: "risk-bg-medium" },
  { key: "high", label: "search.riskShortHigh", bg: "risk-bg-high" },
];

function DistributionBar({
  riskCounts,
  count,
  onDrillDown,
}: {
  riskCounts: Record<RiskLevel, number>;
  count: number;
  onDrillDown: (risk: RiskLevel) => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="flex h-1.5 w-full overflow-hidden rounded-full bg-background-200">
      {RISK_SEGMENTS.map((segment) => {
        const value = riskCounts[segment.key];
        if (value === 0) return null;
        return (
          <Tooltip
            key={segment.key}
            content={`${t(RISK_HINT[segment.key])} · ${t("common.companiesUnit", { count: value })}`}
            className="h-full"
            style={{ width: `${(value / count) * 100}%` }}
          >
            <button
              type="button"
              onClick={() => onDrillDown(segment.key)}
              aria-label={t("search.drillAria", {
                label: t(segment.label),
                count: value,
              })}
              className={`h-full w-full cursor-pointer ${segment.bg} transition-opacity hover:opacity-75`}
            ></button>
          </Tooltip>
        );
      })}
    </div>
  );
}

function GroupMemberRow({
  company,
  keyword,
}: {
  company: Company;
  keyword: string;
}) {
  const { t } = useTranslation();
  const { pick } = useLang();
  return (
    <div className="flex flex-col gap-2 px-3 py-2.5 transition-colors hover:bg-background-200/40 sm:flex-row sm:items-center sm:gap-3">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-background-200 text-foreground-600">
        <i className="ri-building-2-line text-[15px]"></i>
      </span>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1.5">
          <Link
            to={`/company/${company.id}`}
            className="cursor-pointer truncate text-[13px] font-medium text-foreground-950 transition-colors hover:text-primary-400"
          >
            <Highlight text={company.nameCn} query={keyword} />
          </Link>
          <RiskBadge level={company.riskLevel} size="sm" />
        </div>
        <p className="mt-0.5 truncate font-mono text-[11px] text-foreground-500">
          <Highlight text={company.regNo} query={keyword} /> ·{" "}
          {pick(company.country, company.countryEn)} ·{" "}
          {pick(company.industry, company.industryEn)}
        </p>
      </div>

      <div className="flex items-center gap-4 font-mono sm:shrink-0">
        <div className="text-right">
          <p className="text-[10px] text-foreground-500">{t("search.score")}</p>
          <p className="text-sm font-semibold text-foreground-950">
            {company.creditScore}
          </p>
        </div>
        <div className="text-right">
          <p className="text-[10px] text-foreground-500">{t("search.pd")}</p>
          <p className="text-xs text-foreground-800">
            {company.defaultProb.toFixed(1)}%
          </p>
        </div>
      </div>

      <div className="flex shrink-0 gap-1.5">
        <Link
          to={`/score/${company.id}`}
          className="flex cursor-pointer items-center gap-1 whitespace-nowrap rounded-md border border-background-300 px-2 py-1 text-[11px] text-foreground-700 transition-colors hover:border-primary-400 hover:text-primary-400"
        >
          <i className="ri-line-chart-line text-[12px]"></i>
          {t("search.btnScore")}
        </Link>
        <Link
          to={`/report/${company.id}`}
          className="flex cursor-pointer items-center gap-1 whitespace-nowrap rounded-md border border-background-300 px-2 py-1 text-[11px] text-foreground-700 transition-colors hover:border-primary-400 hover:text-primary-400"
        >
          <i className="ri-file-text-line text-[12px]"></i>
          {t("search.btnReport")}
        </Link>
      </div>
    </div>
  );
}

interface GroupedResultsProps {
  groups: CompanyGroup[];
  keyword: string;
  groupKey: GroupKey;
  onDrillDown: (groupValue: string, risk: RiskLevel, label?: string) => void;
}

export default function GroupedResults({
  groups,
  keyword,
  groupKey,
  onDrillDown,
}: GroupedResultsProps) {
  const { t } = useTranslation();
  const { pick } = useLang();
  const [expanded, setExpanded] = useState<string[]>([]);

  useEffect(() => {
    setExpanded([]);
  }, [groupKey]);

  const total = groups.reduce((sum, group) => sum + group.count, 0);
  const allExpanded = groups.length > 0 && expanded.length === groups.length;

  const toggleGroup = (key: string) => {
    setExpanded((prev) =>
      prev.includes(key) ? prev.filter((item) => item !== key) : [...prev, key],
    );
  };

  const toggleAll = () => {
    setExpanded(allExpanded ? [] : groups.map((group) => group.key));
  };

  return (
    <div className="animate-fade-in space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-xs text-foreground-500">
          <i className="ri-group-2-line text-sm"></i>
          {t(
            groupKey === "region"
              ? "search.groupSummaryRegion"
              : "search.groupSummarySector",
            { count: groups.length },
          )}
        </p>
        <button
          type="button"
          onClick={toggleAll}
          className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border border-background-300 px-2.5 py-1.5 text-[11px] text-foreground-700 transition-colors hover:border-primary-400 hover:text-primary-400"
        >
          <i
            className={`ri-${
              allExpanded ? "arrow-up-double-line" : "arrow-down-double-line"
            } text-[13px]`}
          ></i>
          {allExpanded ? t("search.collapseAll") : t("search.expandAll")}
        </button>
      </div>

      {groups.map((group) => {
        const isOpen = expanded.includes(group.key);
        const displayLabel = pick(group.label, group.labelEn);
        const drill = (risk: RiskLevel) => onDrillDown(group.key, risk, displayLabel);
        return (
          <section
            key={group.key}
            className="overflow-hidden rounded-lg border border-background-200 bg-background-100"
          >
            <div className="flex flex-col gap-3 px-4 py-3.5 transition-colors hover:bg-background-200/30 xl:flex-row xl:items-center xl:gap-6">
              <button
                type="button"
                onClick={() => toggleGroup(group.key)}
                className="flex min-w-0 cursor-pointer items-center gap-3 text-left xl:w-64 xl:shrink-0"
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary-500/12 text-primary-400">
                  <i
                    className={`ri-${
                      groupKey === "region" ? "earth-line" : "stack-line"
                    } text-base`}
                  ></i>
                </span>
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-foreground-950">
                    {displayLabel}
                  </p>
                  <p className="mt-0.5 font-mono text-[11px] text-foreground-500">
                    {t("search.groupCount", {
                      count: group.count,
                      pct: Math.round((group.count / total) * 100),
                    })}
                  </p>
                </div>
              </button>

              <div className="flex flex-1 flex-col gap-2">
                <DistributionBar
                  riskCounts={group.riskCounts}
                  count={group.count}
                  onDrillDown={drill}
                />
                <div className="flex flex-wrap items-center gap-1.5">
                  {RISK_SEGMENTS.map((segment) => {
                    const value = group.riskCounts[segment.key];
                    const disabled = value === 0;
                    return (
                      <button
                        key={segment.key}
                        type="button"
                        disabled={disabled}
                        onClick={() => drill(segment.key)}
                        className={`inline-flex whitespace-nowrap ${
                          disabled
                            ? "cursor-not-allowed"
                            : "cursor-pointer transition-opacity hover:opacity-80"
                        }`}
                      >
                        <StatusPill
                          level={segment.key}
                          size="sm"
                          dotSize="xs"
                          className={disabled ? "opacity-45" : ""}
                          label={
                            <>
                              {t(segment.label)} {value}
                              {!disabled && (
                                <i className="ri-arrow-right-s-line text-[12px]"></i>
                              )}
                            </>
                          }
                        />
                      </button>
                    );
                  })}
                  {group.highRiskShare > 0 && (
                    <span className="risk-text-high text-[11px]">
                      {t("search.highRiskShare", { pct: group.highRiskShare })}
                    </span>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-5 xl:shrink-0">
                <div className="text-right">
                  <p className="text-[10px] text-foreground-500">{t("search.avgScore")}</p>
                  <p className="font-mono text-base font-semibold text-foreground-950">
                    {group.avgScore}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-[10px] text-foreground-500">{t("search.avgPd")}</p>
                  <p className="font-mono text-sm text-foreground-800">
                    {group.avgDefaultProb.toFixed(1)}%
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => toggleGroup(group.key)}
                  aria-label={isOpen ? t("search.collapseGroup") : t("search.expandGroup")}
                  className="flex h-7 w-7 cursor-pointer items-center justify-center rounded-md border border-background-300 text-foreground-600 transition-colors hover:border-primary-400 hover:text-primary-400"
                >
                  <i
                    className={`ri-arrow-down-s-line text-base transition-transform ${
                      isOpen ? "rotate-180" : ""
                    }`}
                  ></i>
                </button>
              </div>
            </div>

            {isOpen && (
              <div className="animate-fade-in border-t border-background-200">
                <div className="divide-y divide-background-200/60">
                  {group.companies.map((company) => (
                    <GroupMemberRow
                      key={company.id}
                      company={company}
                      keyword={keyword}
                    />
                  ))}
                </div>
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}