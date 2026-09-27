import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import * as OverviewApi from "@/entities/overview/api/overviewApi";
import PageFrame from "@/features/workbench-layout/ui/PageFrame";
import { handleApiError } from "@/shared/api/http";
import type { ResponseGetOverviewCompany } from "@/shared/api/generated/schema";
import Card from "@/shared/ui/Card";

const CATEGORY_TONE: Record<ResponseGetOverviewCompany["company"]["labelCategory"], string> = {
  healthy: "bg-primary-500/12 text-primary-400",
  distress: "bg-danger-500/12 text-danger-500",
  unlabeled: "bg-background-300/70 text-foreground-600",
};

const availabilityTone = (value: string) => value === "available"
  ? "bg-primary-500/12 text-primary-400"
  : value === "no_records"
    ? "bg-background-300/70 text-foreground-600"
    : "bg-accent-500/10 text-accent-400";

const show = (value: string | number | null | undefined) => value ?? "—";

export default function RealCompanyProfilePage() {
  const { t } = useTranslation();
  const { datasetId = "", companyId = "" } = useParams();
  const [profile, setProfile] = useState<ResponseGetOverviewCompany | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    OverviewApi.requestGetOverviewCompany({ datasetId, companyId })
      .then((data) => {
        if (!active) return;
        setProfile(data);
        setError("");
      })
      .catch((failure) => {
        if (!active) return;
        setProfile(null);
        setError(handleApiError(failure, {
          OVERVIEW_COMPANY_NOT_FOUND: t("realProfile.notFound.title"),
        }));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [companyId, datasetId, t]);

  if (!profile) {
    return (
      <PageFrame title={t("realProfile.title")} subtitle={t("realProfile.subtitle")} dataset>
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-background-300 bg-background-100 px-6 py-20 text-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-full bg-background-200 text-foreground-500">
            <i className={`${loading ? "ri-loader-4-line animate-spin" : "ri-building-4-line"} text-2xl`} />
          </span>
          <h3 className="mt-4 text-[15px] font-semibold text-foreground-950">
            {loading ? t("realProfile.loading") : error || t("realProfile.notFound.title")}
          </h3>
          {!loading && <p className="mt-1.5 max-w-md text-sm text-foreground-500">{t("realProfile.notFound.desc")}</p>}
          {!loading && <Link to="/search" className="mt-5 rounded-md bg-primary-500 px-4 py-2 text-xs font-medium text-background-50 hover:bg-primary-600">{t("realProfile.back")}</Link>}
        </div>
      </PageFrame>
    );
  }

  const { company, facts, relations, groups, dataAvailability, dataset } = profile;
  const factItems = [
    ["uen", company.companyId],
    ["country", facts.country],
    ["status", company.status],
    ["age", company.ageYears === null ? null : t("realProfile.value.years", { value: company.ageYears.toFixed(1) })],
    ["operatingMonths", facts.setupTimeMonths === null ? null : facts.setupTimeMonths.toFixed(1)],
    ["ssic", company.industryCode],
    ["ssic2", facts.industryDivisionCode],
    ["officers", facts.officerCount],
    ["nameChanges", facts.nameChangeCount],
    ["hasUnit", facts.hasUnit === null ? null : t(`realProfile.value.${facts.hasUnit ? "yes" : "no"}`)],
    ["registeredCapital", facts.registeredCapital],
    ["paidCapital", facts.paidCapital],
  ] as const;
  const availabilityItems = Object.entries(dataAvailability) as Array<[keyof typeof dataAvailability, string]>;

  return (
    <PageFrame
      title={t("realProfile.title")}
      subtitle={t("realProfile.subtitle")}
      dataset
      actions={<Link to="/search" className="flex items-center gap-1.5 rounded-md border border-background-300 px-3 py-2 text-xs text-foreground-700 hover:border-primary-400 hover:text-primary-400"><i className="ri-arrow-left-line text-sm" />{t("realProfile.back")}</Link>}
    >
      <div className="space-y-4">
        <section className="overflow-hidden rounded-lg border border-background-200 bg-background-100">
          <div className="flex flex-col gap-5 p-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="flex min-w-0 gap-4">
              <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-lg bg-primary-500/12 text-primary-400"><i className="ri-building-2-line text-2xl" /></span>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2.5">
                  <h2 className="font-heading text-xl font-semibold text-foreground-950">{company.name}</h2>
                  <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${CATEGORY_TONE[company.labelCategory]}`}>{t(`search.category.${company.labelCategory}`)}</span>
                </div>
                <p className="mt-1 text-sm text-foreground-600">{company.status}</p>
                <div className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1.5 font-mono text-[11px] text-foreground-500">
                  <span>UEN {company.companyId}</span>
                  <span>{dataset.country}</span>
                  <span>{company.industryCode ? `SSIC ${company.industryCode}` : "SSIC —"}</span>
                </div>
              </div>
            </div>
            <div className="rounded-md border border-accent-500/25 bg-accent-500/8 px-4 py-3 lg:max-w-sm">
              <p className="text-xs font-semibold text-accent-400">{t("realProfile.observed.title")}</p>
              <p className="mt-1 text-xs leading-relaxed text-foreground-600">{t("realProfile.observed.description")}</p>
            </div>
          </div>
        </section>

        <div className="rounded-lg border border-primary-500/25 bg-primary-500/8 px-4 py-3">
          <p className="text-xs font-semibold text-primary-400">{t("realProfile.boundary.title")}</p>
          <p className="mt-1 text-xs leading-relaxed text-foreground-600">{t("realProfile.boundary.description")}</p>
        </div>

        <Card title={t("realProfile.facts.title")} subtitle={t("realProfile.facts.subtitle")} icon="ri-file-list-3-line" bodyClassName="p-4">
          <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {factItems.map(([key, value]) => <div key={key} className="rounded-md bg-background-50 px-3 py-3"><dt className="text-[11px] text-foreground-500">{t(`realProfile.facts.${key}`)}</dt><dd className="mt-1 break-words font-mono text-sm font-medium text-foreground-900">{show(value)}</dd></div>)}
          </dl>
        </Card>

        <div className="grid gap-4 lg:grid-cols-3">
          <Card title={t("realProfile.relations.title")} subtitle={t("realProfile.relations.subtitle")} icon="ri-node-tree" className="lg:col-span-2" bodyClassName="p-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-md bg-background-50 px-3 py-3"><p className="text-[11px] text-foreground-500">{t("realProfile.relations.total")}</p><p className="mt-1 font-mono text-xl font-semibold text-foreground-950">{relations.totalCount.toLocaleString()}</p></div>
              <div className="rounded-md bg-background-50 px-3 py-3"><p className="text-[11px] text-foreground-500">{t("realProfile.relations.types")}</p><div className="mt-1 flex flex-wrap gap-1.5">{relations.byType.length ? relations.byType.map((item) => <span key={item.type} className="rounded-full bg-secondary-500/12 px-2 py-0.5 text-[11px] text-secondary-300">{t(`realProfile.relationType.${item.type}`, { defaultValue: item.type })} · {item.count}</span>) : <span className="text-sm text-foreground-600">—</span>}</div></div>
            </div>
            <div className="mt-3 rounded-md border border-accent-500/20 bg-accent-500/6 px-3 py-2 text-[11px] leading-relaxed text-foreground-600">{t("realProfile.relations.warning")}</div>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[620px] text-left text-xs">
                <thead><tr className="border-b border-background-200 text-[10px] uppercase tracking-wide text-foreground-500"><th className="px-2 py-2 font-medium">{t("realProfile.relations.company")}</th><th className="px-2 py-2 font-medium">{t("realProfile.relations.type")}</th><th className="px-2 py-2 font-medium">{t("realProfile.relations.status")}</th><th className="px-2 py-2 text-right font-medium">{t("realProfile.relations.weight")}</th></tr></thead>
                <tbody>{relations.neighbors.map((neighbor) => <tr key={`${neighbor.relationType}-${neighbor.companyId}`} className="border-b border-background-200/60 last:border-0"><td className="px-2 py-2.5"><p className="font-medium text-foreground-900">{neighbor.name}</p><p className="mt-0.5 font-mono text-[10px] text-foreground-500">{neighbor.companyId}</p></td><td className="px-2 py-2.5 text-foreground-700">{t(`realProfile.relationType.${neighbor.relationType}`, { defaultValue: neighbor.relationType })}</td><td className="px-2 py-2.5 text-foreground-600">{neighbor.status}</td><td className="px-2 py-2.5 text-right font-mono text-foreground-700">{neighbor.weight.toFixed(4)}</td></tr>)}</tbody>
              </table>
              {relations.neighbors.length === 0 && <p className="py-8 text-center text-xs text-foreground-500">{t("realProfile.relations.empty")}</p>}
            </div>
            {relations.truncated && <p className="mt-2 text-[11px] text-foreground-500">{t("realProfile.relations.truncated", { shown: relations.displayedCount, total: relations.totalCount })}</p>}
          </Card>

          <Card title={t("realProfile.groups.title")} subtitle={t("realProfile.groups.subtitle")} icon="ri-group-2-line" bodyClassName="space-y-3 p-4">
            {groups.map((group) => <div key={group.type} className="rounded-md bg-background-50 px-3 py-3"><p className="text-[11px] text-foreground-500">{t(`realProfile.groups.${group.type}`)}</p><p className="mt-1 break-all font-mono text-sm font-semibold text-foreground-900">{group.value}</p><p className="mt-1 text-[10px] text-foreground-500">{t("realProfile.groups.members", { count: group.memberCount.toLocaleString() })}</p></div>)}
          </Card>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <Card title={t("realProfile.availability.title")} subtitle={t("realProfile.availability.subtitle")} icon="ri-database-2-line" bodyClassName="grid gap-2 p-4 sm:grid-cols-2">
            {availabilityItems.map(([key, value]) => <div key={key} className="flex items-center justify-between gap-3 rounded-md bg-background-50 px-3 py-2.5"><span className="text-xs text-foreground-700">{t(`realProfile.availability.field.${key}`)}</span><span className={`rounded-full px-2 py-0.5 text-[10px] ${availabilityTone(value)}`}>{t(`realProfile.availability.status.${value}`)}</span></div>)}
          </Card>
          <Card title={t("realProfile.model.title")} subtitle={t("realProfile.model.subtitle")} icon="ri-cpu-line" bodyClassName="p-4">
            <div className="rounded-md border border-dashed border-background-300 bg-background-50 p-4"><p className="text-sm font-semibold text-foreground-900">{t("realProfile.model.notRun")}</p><p className="mt-1 text-xs leading-relaxed text-foreground-600">{t("realProfile.model.description")}</p><Link to="/modeling" className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-primary-400 hover:text-primary-300">{t("realProfile.model.openWorkbench")}<i className="ri-arrow-right-line" /></Link></div>
          </Card>
        </div>

        <Card title={t("realProfile.provenance.title")} subtitle={dataset.name} icon="ri-shield-check-line" bodyClassName="p-4">
          <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div><dt className="text-[11px] text-foreground-500">{t("realProfile.provenance.dataset")}</dt><dd className="mt-1 font-mono text-xs text-foreground-800">{dataset.id}</dd></div>
            <div><dt className="text-[11px] text-foreground-500">{t("realProfile.provenance.generated")}</dt><dd className="mt-1 font-mono text-xs text-foreground-800">{dataset.generatedAt}</dd></div>
            <div><dt className="text-[11px] text-foreground-500">{t("realProfile.provenance.scope")}</dt><dd className="mt-1 text-xs text-foreground-800">{dataset.sourceScope}</dd></div>
            <div><dt className="text-[11px] text-foreground-500">SHA-256</dt><dd title={dataset.sourceArchiveSha256} className="mt-1 truncate font-mono text-xs text-foreground-800">{dataset.sourceArchiveSha256}</dd></div>
          </dl>
          <div className="mt-4 space-y-1.5">{profile.warnings.map((warning) => <p key={warning} className="flex gap-2 text-[11px] leading-relaxed text-foreground-600"><i className="ri-information-line mt-0.5 text-accent-400" />{t(`overview.warnings.${warning}`)}</p>)}</div>
        </Card>
      </div>
    </PageFrame>
  );
}
