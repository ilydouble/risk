import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import PageFrame from "@/features/workbench-layout/ui/PageFrame";
import ModelHero from "@/pages/model/components/ModelHero";
import ModelArchitectureCard from "@/pages/model/components/ModelArchitectureCard";
import TrainingDataCard from "@/pages/model/components/TrainingDataCard";
import GlobalImportanceCard from "@/pages/model/components/GlobalImportanceCard";
import VersionHistoryCard from "@/pages/model/components/VersionHistoryCard";
import DriftMonitorCard from "@/pages/model/components/DriftMonitorCard";
import GovernanceCard from "@/pages/model/components/GovernanceCard";
import ModelResourceLinks from "@/pages/model/components/ModelResourceLinks";
import { buildEvalDashboard } from "@/pages/model/lib/eval";
import { useLang } from "@/shared/lib/useLang";

export default function ModelArchivePage() {
  const { t } = useTranslation();
  const { lang } = useLang();
  const dashboard = useMemo(() => buildEvalDashboard(undefined, lang), [lang]);

  return (
    <PageFrame
      title={t("model.archive.title")}
      subtitle={t("model.archive.subtitle")}
      modelTabs
      actions={
        <Link
          to="/"
          className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border border-background-300 px-3 py-2 text-xs text-foreground-700 transition-colors hover:border-primary-400 hover:text-primary-400"
        >
          <i className="ri-arrow-left-line text-sm"></i>
          {t("model.archive.backToOverview")}
        </Link>
      }
    >
      <div className="space-y-4">
        <ModelHero />

        <div className="animate-fade-up" style={{ animationDelay: "40ms" }}>
          <ModelArchitectureCard />
        </div>

        <div className="animate-fade-up" style={{ animationDelay: "80ms" }}>
          <TrainingDataCard />
        </div>

        <div className="animate-fade-up" style={{ animationDelay: "120ms" }}>
          <GlobalImportanceCard
            rows={dashboard.ablation.rows}
            baselineAuc={dashboard.ablation.baselineAuc}
          />
        </div>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <div className="animate-fade-up" style={{ animationDelay: "160ms" }}>
            <VersionHistoryCard />
          </div>
          <div className="animate-fade-up" style={{ animationDelay: "200ms" }}>
            <DriftMonitorCard />
          </div>
        </div>

        <div className="animate-fade-up" style={{ animationDelay: "240ms" }}>
          <GovernanceCard />
        </div>

        <div style={{ animationDelay: "280ms" }}>
          <ModelResourceLinks />
        </div>
      </div>
    </PageFrame>
  );
}