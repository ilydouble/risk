import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import PageFrame from "@/features/workbench-layout/ui/PageFrame";
import ModelHeader from "@/pages/model/components/ModelHeader";
import EvalVersionSwitcher from "@/pages/model/components/EvalVersionSwitcher";
import MetricCards from "@/pages/model/components/MetricCards";
import CalibrationCard from "@/pages/model/components/CalibrationCard";
import AblationCard from "@/pages/model/components/AblationCard";
import ExtrapolationCard from "@/pages/model/components/ExtrapolationCard";
import ReproduceModal from "@/pages/model/components/ReproduceModal";
import {
  buildEvalDashboard,
  EVAL_MODEL_VERSION,
  isEvalVersion,
} from "@/pages/model/lib/eval";
import { useReproduce } from "@/pages/model/hooks/useReproduce";
import { useLang } from "@/shared/lib/useLang";
import { modelVersionHistory } from "@/features/demo-scenarios/model/fixtures/modelCard";

export default function ModelPage() {
  const { t } = useTranslation();
  const { lang } = useLang();
  const [searchParams] = useSearchParams();
  const requestedVersion = searchParams.get("version");
  const version = isEvalVersion(requestedVersion)
    ? (requestedVersion as string)
    : EVAL_MODEL_VERSION;

  const dashboard = useMemo(
    () => buildEvalDashboard(version, lang),
    [version, lang],
  );
  const repro = useReproduce(dashboard, lang);

  const isCurrent = version === EVAL_MODEL_VERSION;
  const activeEntry = modelVersionHistory.find((entry) => entry.version === version);

  return (
    <PageFrame
      title={t("model.dashboard.title")}
      subtitle={t("model.dashboard.subtitle")}
      modelTabs
      actions={
        <Link
          to="/"
          className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border border-background-300 px-3 py-2 text-xs text-foreground-700 transition-colors hover:border-primary-400 hover:text-primary-400"
        >
          <i className="ri-arrow-left-line text-sm"></i>
          {t("model.dashboard.backToOverview")}
        </Link>
      }
    >
      <div className="space-y-4">
        <EvalVersionSwitcher activeVersion={version} />

        {!isCurrent && (
          <section className="animate-fade-up flex flex-wrap items-center gap-3 rounded-lg border border-accent-500/25 bg-accent-500/8 px-4 py-3">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-accent-500/15 text-accent-400">
              <i className="ri-history-line text-[14px]"></i>
            </span>
            <p className="text-xs leading-relaxed text-foreground-700">
              {t("model.dashboard.historyBanner", {
                version,
                date: activeEntry ? activeEntry.date : "",
              })}
            </p>
            <Link
              to="/model"
              className="ml-auto flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border border-accent-500/40 px-3 py-1.5 text-xs text-accent-400 transition-colors hover:bg-accent-500/12"
            >
              <i className="ri-arrow-go-back-line text-[13px]"></i>
              {t("model.dashboard.backToCurrent")}
            </Link>
          </section>
        )}

        <ModelHeader dashboard={dashboard} />

        <MetricCards metrics={dashboard.metrics} onReproduce={repro.start} />

        <CalibrationCard
          curve={dashboard.calibration}
          onReproduce={() => repro.start("calibration")}
        />

        <AblationCard
          study={dashboard.ablation}
          onReproduce={() => repro.start("ablation")}
        />

        <ExtrapolationCard
          study={dashboard.extrapolation}
          onReproduce={() => repro.start("extrapolation")}
        />
      </div>

      <ReproduceModal
        run={repro.run}
        stepIndex={repro.stepIndex}
        done={repro.done}
        onClose={repro.close}
        onRestart={repro.restart}
      />
    </PageFrame>
  );
}