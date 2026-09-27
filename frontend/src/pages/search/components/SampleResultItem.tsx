import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import type { components } from "@/shared/api/generated/schema";
import Highlight from "@/pages/search/components/Highlight";

type OverviewSampleCompany = components["schemas"]["OverviewSampleCompanyDTO"];

const CATEGORY_TONE: Record<OverviewSampleCompany["labelCategory"], string> = {
  healthy: "bg-primary-500/12 text-primary-400",
  distress: "bg-danger-500/12 text-danger-500",
  unlabeled: "bg-background-300/70 text-foreground-600",
};

export default function SampleResultItem({
  company,
  datasetId,
  keyword,
}: {
  company: OverviewSampleCompany;
  datasetId: string;
  keyword: string;
}) {
  const { t } = useTranslation();
  return (
    <article className="rounded-lg border border-background-200 bg-background-100 p-4 transition-colors hover:border-background-300">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-md bg-background-200 text-foreground-600">
          <i className="ri-building-2-line text-xl" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-[15px] font-semibold text-foreground-950">
              <Highlight text={company.name} query={keyword} />
            </h3>
            <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${CATEGORY_TONE[company.labelCategory]}`}>
              {t(`search.category.${company.labelCategory}`)}
            </span>
            <span className="rounded-full bg-accent-500/10 px-2 py-0.5 text-[10px] text-accent-400">
              {t("search.realSample")}
            </span>
          </div>
          <p className="mt-1 text-xs text-foreground-600">
            <Highlight text={company.status} query={keyword} />
          </p>
          <p className="mt-2 font-mono text-[11px] text-foreground-500">
            UEN <Highlight text={company.companyId} query={keyword} />
          </p>
        </div>
        <dl className="grid shrink-0 grid-cols-3 gap-5 text-right lg:w-72">
          <div>
            <dt className="text-[10px] text-foreground-500">{t("search.age")}</dt>
            <dd className="mt-1 font-mono text-sm text-foreground-900">
              {company.ageYears === null ? "—" : company.ageYears.toFixed(1)}
            </dd>
          </div>
          <div>
            <dt className="text-[10px] text-foreground-500">SSIC</dt>
            <dd className="mt-1 font-mono text-sm text-foreground-900">
              {company.industryCode ?? "—"}
            </dd>
          </div>
          <div>
            <dt className="text-[10px] text-foreground-500">{t("search.relations")}</dt>
            <dd className="mt-1 font-mono text-sm text-foreground-900">
              {company.relationCount}
            </dd>
          </div>
        </dl>
        <Link
          to={`/company/${encodeURIComponent(datasetId)}/${encodeURIComponent(company.companyId)}`}
          className="flex shrink-0 items-center gap-1.5 rounded-md border border-primary-500/30 px-3 py-2 text-[11px] font-medium text-primary-400 transition-colors hover:border-primary-400 hover:bg-primary-500/8"
        >
          <i className="ri-building-line text-sm" />
          {t("search.profileUnavailable")}
        </Link>
      </div>
    </article>
  );
}
