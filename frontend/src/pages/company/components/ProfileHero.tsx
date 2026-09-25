import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import RiskBadge from "@/components/base/RiskBadge";
import StatusPill from "@/components/base/StatusPill";
import { useLang } from "@/hooks/useLang";
import type { Company } from "@/types";

interface ProfileHeroProps {
  company: Company;
  onAddToBatch: () => void;
}

const SCORE_MAX = 1000;

export default function ProfileHero({ company, onAddToBatch }: ProfileHeroProps) {
  const { t } = useTranslation();
  const { isEn, pick } = useLang();

  const scorePercent = Math.min(
    100,
    Math.round((company.creditScore / SCORE_MAX) * 100),
  );
  const tags = isEn && company.tagsEn ? company.tagsEn : company.tags;

  const metrics = [
    {
      key: "score",
      label: t("company.hero.score"),
      value: String(company.creditScore),
      unit: t("company.hero.scoreUnit", { max: SCORE_MAX }),
      icon: "ri-shield-star-line",
      tone: "text-primary-400",
      showBar: true,
    },
    {
      key: "pd",
      label: t("company.hero.pd"),
      value: `${company.defaultProb.toFixed(1)}%`,
      unit: t("company.hero.pdUnit"),
      icon: "ri-alert-line",
      tone: "text-accent-400",
      showBar: false,
    },
    {
      key: "limit",
      label: t("company.hero.limit"),
      value: company.creditLimit,
      unit: t("company.hero.limitUnit"),
      icon: "ri-hand-coin-line",
      tone: "text-foreground-900",
      showBar: false,
    },
    {
      key: "updated",
      label: t("company.hero.updated"),
      value: company.updatedAt.split(" ")[0],
      unit: company.updatedAt.split(" ")[1],
      icon: "ri-time-line",
      tone: "text-foreground-900",
      showBar: false,
    },
  ];

  const actions = [
    { to: `/graph?company=${company.id}`, label: t("company.hero.actionGraph"), icon: "ri-node-tree" },
    { to: `/score/${company.id}`, label: t("company.hero.actionScore"), icon: "ri-bar-chart-box-line" },
    { to: `/report/${company.id}`, label: t("company.hero.actionReport"), icon: "ri-file-text-line" },
    { to: `/decision/${company.id}`, label: t("company.hero.actionDecision"), icon: "ri-shield-check-line" },
  ];

  return (
    <section className="animate-fade-up overflow-hidden rounded-lg border border-background-200 bg-background-100">
      <div className="flex flex-col gap-5 p-5 xl:flex-row xl:items-start xl:justify-between">
        <div className="flex min-w-0 gap-4">
          <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-lg bg-primary-500/12 text-primary-400">
            <i className="ri-building-2-line text-2xl"></i>
          </span>

          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2.5">
              <h2 className="font-heading text-xl font-semibold text-foreground-950">
                {pick(company.nameCn, company.nameEn)}
              </h2>
              <RiskBadge level={company.riskLevel} />
              <StatusPill level="low" label={t("company.hero.active")} size="sm" />
            </div>

            <p className="mt-1 text-sm text-foreground-600">
              {isEn ? company.nameCn : company.nameEn}
            </p>

            <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1.5 font-mono text-[11px] text-foreground-500">
              <span className="flex items-center gap-1.5">
                <i className="ri-hashtag text-[11px]"></i>
                {company.regNo}
              </span>
              <span className="flex items-center gap-1.5">
                <i className="ri-earth-line text-[11px]"></i>
                {pick(company.country, company.countryEn)}
              </span>
              <span className="flex items-center gap-1.5">
                <i className="ri-stack-line text-[11px]"></i>
                {pick(company.industry, company.industryEn)}
              </span>
              <span className="flex items-center gap-1.5">
                <i className="ri-database-2-line text-[11px]"></i>
                {company.id}
              </span>
            </div>

            <div className="mt-3 flex flex-wrap gap-1.5">
              {tags.map((tag) => (
                <span
                  key={tag}
                  className="rounded-full bg-secondary-500/12 px-2.5 py-0.5 text-[11px] text-secondary-300"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
        </div>

        <div className="grid shrink-0 grid-cols-1 gap-3 sm:grid-cols-2 xl:w-[420px]">
          {metrics.map((metric) => (
            <div
              key={metric.key}
              className="rounded-md border border-background-200 bg-background-50 p-3"
            >
              <div className="flex items-center gap-1.5">
                <span className="flex h-4 w-4 items-center justify-center text-foreground-500">
                  <i className={`${metric.icon} text-[13px]`}></i>
                </span>
                <span className="text-[11px] text-foreground-500">
                  {metric.label}
                </span>
              </div>
              <p className="mt-1.5 flex items-baseline gap-1">
                <span
                  className={`font-mono text-lg font-semibold tracking-tight ${metric.tone}`}
                >
                  {metric.value}
                </span>
                <span className="text-[10px] text-foreground-500">
                  {metric.unit}
                </span>
              </p>
              {metric.showBar && (
                <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-background-200">
                  <span
                    className="block h-full rounded-full bg-primary-500"
                    style={{ width: `${scorePercent}%` }}
                  ></span>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-background-200/70 bg-background-50 px-5 py-3">
        {actions.map((action) => (
          <Link
            key={action.to}
            to={action.to}
            className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border border-background-300 px-3 py-2 text-xs text-foreground-700 transition-colors hover:border-primary-400 hover:text-primary-400"
          >
            <i className={`${action.icon} text-sm`}></i>
            {action.label}
          </Link>
        ))}
        <button
          type="button"
          onClick={onAddToBatch}
          className="ml-auto flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md bg-primary-500 px-3.5 py-2 text-xs font-medium text-background-50 transition-colors hover:bg-primary-600"
        >
          <i className="ri-add-circle-line text-sm"></i>
          {t("company.hero.addToBatch")}
        </button>
      </div>
    </section>
  );
}