import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import PageFrame from "@/features/workbench-layout/ui/PageFrame";
import ProfileHero from "@/pages/company/components/ProfileHero";
import BusinessInfoCard from "@/pages/company/components/BusinessInfoCard";
import RiskTagCloud from "@/pages/company/components/RiskTagCloud";
import FiveCPanel from "@/pages/company/components/FiveCPanel";
import ChangeTimeline from "@/pages/company/components/ChangeTimeline";
import RelatedPartiesPanel from "@/pages/company/components/RelatedPartiesPanel";
import { useLang } from "@/shared/lib/useLang";
import * as CompanyApi from "@/entities/company/api/companyApi";
import { handleApiError } from "@/shared/api/http";
import type { Company, CompanyProfile } from "@/entities/demo/model/types";
import DocumentPanel from "@/pages/company/components/DocumentPanel";

export default function CompanyPage() {
  const { t } = useTranslation();
  const { pick } = useLang();
  const { id } = useParams();
  const [company, setCompany] = useState<Company | null>(null);
  const [profile, setProfile] = useState<CompanyProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    CompanyApi.requestGetCompany({ id: id ?? "" })
      .then((data) => {
        if (!active) return;
        setCompany(data.company);
        setProfile(data.profile);
        setError("");
      })
      .catch((failure) => { if (active) setError(handleApiError(failure, { COMPANY_NOT_FOUND: t("company.notFound.title") })); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [id, t]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 2600);
    return () => window.clearTimeout(timer);
  }, [toast]);

  if (!company || !profile) {
    return (
      <PageFrame
        title={t("company.title")}
        subtitle={t("company.notFound.shellSubtitle")}
      >
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-background-300 bg-background-100 px-6 py-20 text-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-full bg-background-200 text-foreground-500">
            <i className="ri-building-4-line text-2xl"></i>
          </span>
          <h3 className="mt-4 text-[15px] font-semibold text-foreground-950">
            {loading ? "…" : error || t("company.notFound.title")}
          </h3>
          <p className="mt-1.5 max-w-md text-sm text-foreground-500">
            {t("company.notFound.desc", { id })}
          </p>
          <Link
            to="/search"
            className="mt-5 flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md bg-primary-500 px-4 py-2 text-xs font-medium text-background-50 transition-colors hover:bg-primary-600"
          >
            <i className="ri-search-line text-sm"></i>
            {t("company.notFound.back")}
          </Link>
        </div>
      </PageFrame>
    );
  }

  const headCount = profile.riskFlags.filter((f) => f.level === "high").length;

  return (
    <PageFrame
      title={t("company.title")}
      subtitle={t("company.subtitle")}
      companyId={company.id}
      actions={
        <Link
          to="/search"
          className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border border-background-300 px-3 py-2 text-xs text-foreground-700 transition-colors hover:border-background-400 hover:text-foreground-950"
        >
          <i className="ri-arrow-left-line text-sm"></i>
          {t("company.backToResults")}
        </Link>
      }
    >
      <div className="space-y-4">
        <ProfileHero
          company={company}
          onAddToBatch={() =>
            setToast(
              t("company.toastAdded", {
                name: pick(company.nameCn, company.nameEn),
              }),
            )
          }
        />

        <section className="animate-fade-up flex gap-3 rounded-lg border border-accent-500/30 bg-accent-500/10 p-4">
          <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-accent-500/20 text-accent-400">
            <i className="ri-file-paper-2-line text-[15px]"></i>
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-[13px] font-semibold text-foreground-950">
                {t("company.conclusion.title")}
              </p>
              <span className="rounded-full bg-background-100/70 px-2 py-0.5 font-mono text-[10px] text-foreground-600">
                {t("company.conclusion.modelConfidence", {
                  version: "v4.2",
                  pct: 92,
                })}
              </span>
              <span className="rounded-full bg-background-100/70 px-2 py-0.5 font-mono text-[10px] text-foreground-600">
                {t("company.conclusion.highSignals", { count: headCount })}
              </span>
            </div>
            <p className="mt-1.5 text-xs leading-relaxed text-foreground-700">
              {pick(profile.summary, profile.summaryEn)}
            </p>
          </div>
        </section>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <div className="animate-fade-up lg:col-span-2" style={{ animationDelay: "40ms" }}>
            <BusinessInfoCard
              company={company}
              facts={profile.facts}
              factsEn={profile.factsEn}
            />
          </div>
          <div className="animate-fade-up" style={{ animationDelay: "80ms" }}>
            <RiskTagCloud flags={profile.riskFlags} />
          </div>
        </div>

        <div className="animate-fade-up" style={{ animationDelay: "120ms" }}>
          <FiveCPanel dimensions={profile.fiveC} />
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <div
            className="animate-fade-up lg:col-span-2"
            style={{ animationDelay: "160ms" }}
          >
            <ChangeTimeline events={profile.timeline} />
          </div>
          <div className="animate-fade-up" style={{ animationDelay: "200ms" }}>
            <RelatedPartiesPanel parties={profile.relatedParties} />
          </div>
        </div>

        <DocumentPanel companyId={company.id} />
      </div>

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
