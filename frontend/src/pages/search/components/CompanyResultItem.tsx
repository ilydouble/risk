import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useLang } from "@/shared/lib/useLang";
import RiskBadge from "@/entities/risk/ui/RiskBadge";
import Highlight from "@/pages/search/components/Highlight";
import type { Company } from "@/entities/demo/model/types";

interface CompanyResultItemProps {
  company: Company;
  keyword: string;
}

export default function CompanyResultItem({
  company,
  keyword,
}: CompanyResultItemProps) {
  const { t } = useTranslation();
  const { isEn, pick } = useLang();
  const tags = isEn && company.tagsEn ? company.tagsEn : company.tags;
  return (
    <article className="group rounded-lg border border-background-200 bg-background-100 p-4 transition-colors duration-300 hover:border-background-300">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-md bg-background-200 text-foreground-600">
          <i className="ri-building-2-line text-xl"></i>
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Link
              to={`/company/${company.id}`}
              className="cursor-pointer text-[15px] font-semibold text-foreground-950 transition-colors hover:text-primary-400"
            >
              <Highlight text={company.nameCn} query={keyword} />
            </Link>
            <RiskBadge level={company.riskLevel} size="sm" />
          </div>

          <p className="mt-1 truncate text-xs text-foreground-500">
            <Highlight text={company.nameEn} query={keyword} />
          </p>

          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[11px] text-foreground-500">
            <span className="flex items-center gap-1">
              <i className="ri-hashtag text-[11px]"></i>
              <Highlight text={company.regNo} query={keyword} />
            </span>
            <span className="flex items-center gap-1">
              <i className="ri-map-pin-line text-[11px]"></i>
              {pick(company.country, company.countryEn)}
            </span>
            <span className="flex items-center gap-1">
              <i className="ri-price-tag-3-line text-[11px]"></i>
              {pick(company.industry, company.industryEn)}
            </span>
          </div>

          <div className="mt-2.5 flex flex-wrap gap-1.5">
            {tags.map((tag) => (
              <span
                key={tag}
                className="rounded-full bg-secondary-500/12 px-2 py-0.5 text-[11px] text-secondary-300"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>

        <div className="flex shrink-0 flex-col gap-2 lg:w-64 lg:items-end">
          <div className="flex items-end gap-4 lg:justify-end">
            <div className="text-right">
              <p className="text-[11px] text-foreground-500">{t("search.score")}</p>
              <p className="font-mono text-xl font-semibold leading-tight text-foreground-950">
                {company.creditScore}
              </p>
            </div>
            <div className="text-right">
              <p className="text-[11px] text-foreground-500">{t("search.pd")}</p>
              <p className="font-mono text-sm leading-tight text-foreground-800">
                {company.defaultProb.toFixed(1)}%
              </p>
            </div>
            <div className="text-right">
              <p className="text-[11px] text-foreground-500">{t("search.limit")}</p>
              <p className="font-mono text-sm leading-tight text-foreground-800">
                {company.creditLimit}
              </p>
            </div>
          </div>

          <p className="font-mono text-[10px] text-foreground-500 lg:text-right">
            {t("search.recentEval", { date: company.updatedAt })}
          </p>

          <div className="flex flex-wrap gap-1.5 lg:justify-end">
            <Link
              to={`/company/${company.id}`}
              className="flex cursor-pointer items-center gap-1 whitespace-nowrap rounded-md border border-background-300 px-2.5 py-1.5 text-[11px] text-foreground-700 transition-colors hover:border-primary-400 hover:text-primary-400"
            >
              <i className="ri-user-search-line text-[13px]"></i>
              {t("search.btnProfile")}
            </Link>
            <Link
              to={`/score/${company.id}`}
              className="flex cursor-pointer items-center gap-1 whitespace-nowrap rounded-md border border-background-300 px-2.5 py-1.5 text-[11px] text-foreground-700 transition-colors hover:border-primary-400 hover:text-primary-400"
            >
              <i className="ri-line-chart-line text-[13px]"></i>
              {t("search.btnScore")}
            </Link>
            <Link
              to={`/report/${company.id}`}
              className="flex cursor-pointer items-center gap-1 whitespace-nowrap rounded-md border border-background-300 px-2.5 py-1.5 text-[11px] text-foreground-700 transition-colors hover:border-primary-400 hover:text-primary-400"
            >
              <i className="ri-file-text-line text-[13px]"></i>
              {t("search.btnReport")}
            </Link>
          </div>
        </div>
      </div>
    </article>
  );
}