import { useMemo } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import AppShell from "@/components/feature/AppShell";
import ScoreOverviewHero from "@/pages/score/components/ScoreOverviewHero";
import ShapWaterfall from "@/pages/score/components/ShapWaterfall";
import ShapFeatureTable from "@/pages/score/components/ShapFeatureTable";
import ModelExplainCard from "@/pages/score/components/ModelExplainCard";
import CommunityComparison from "@/pages/score/components/CommunityComparison";
import { findCompany, resolveProfile } from "@/pages/company/lib/profile";
import { buildScoreDetail } from "@/pages/score/lib/score";
import { useLang } from "@/hooks/useLang";

export default function ScorePage() {
  const { t } = useTranslation();
  const { lang } = useLang();
  const { id } = useParams();
  const company = useMemo(() => findCompany(id), [id]);

  const detail = useMemo(
    () =>
      company ? buildScoreDetail(company, resolveProfile(company), lang) : null,
    [company, lang],
  );

  if (!company || !detail) {
    return (
      <AppShell title={t("score.title")} subtitle={t("score.notFound.shellSubtitle")}>
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-background-300 bg-background-100 px-6 py-20 text-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-full bg-background-200 text-foreground-500">
            <i className="ri-bar-chart-box-line text-2xl"></i>
          </span>
          <h3 className="mt-4 text-[15px] font-semibold text-foreground-950">
            {t("score.notFound.title")}
          </h3>
          <p className="mt-1.5 max-w-md text-sm text-foreground-500">
            {t("score.notFound.desc", { id })}
          </p>
          <Link
            to="/search"
            className="mt-5 flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md bg-primary-500 px-4 py-2 text-xs font-medium text-background-50 transition-colors hover:bg-primary-600"
          >
            <i className="ri-search-line text-sm"></i>
            {t("score.notFound.back")}
          </Link>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell
      title={t("score.title")}
      subtitle={t("score.subtitle")}
      companyId={company.id}
    >
      <div className="space-y-4">
        <ScoreOverviewHero company={company} detail={detail} />

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="animate-fade-up" style={{ animationDelay: "40ms" }}>
            <ShapWaterfall
              features={detail.features}
              baseValue={detail.baseValue}
              finalScore={detail.finalScore}
            />
          </div>
          <div className="animate-fade-up" style={{ animationDelay: "80ms" }}>
            <ModelExplainCard detail={detail} />
          </div>
        </div>

        <div className="animate-fade-up" style={{ animationDelay: "120ms" }}>
          <ShapFeatureTable features={detail.features} />
        </div>

        <div className="animate-fade-up" style={{ animationDelay: "160ms" }}>
          <CommunityComparison company={company} benchmarks={detail.benchmarks} />
        </div>
      </div>
    </AppShell>
  );
}