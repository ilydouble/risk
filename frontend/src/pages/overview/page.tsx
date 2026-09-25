import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import PageFrame from "@/features/workbench-layout/ui/PageFrame";
import Card from "@/shared/ui/Card";
import StatCard from "@/shared/ui/StatCard";
import DemoBanner from "@/pages/overview/components/DemoBanner";
import EvaluationTrendChart from "@/pages/overview/components/EvaluationTrendChart";
import RiskDistributionChart from "@/pages/overview/components/RiskDistributionChart";
import SystemStatusPanel from "@/pages/overview/components/SystemStatusPanel";
import RecentEvaluations from "@/pages/overview/components/RecentEvaluations";
import { modelMetrics, overviewStats } from "@/features/demo-scenarios/model/fixtures/overview";

const RANGES = [
  { key: 7, labelKey: "overview.ranges.d7" },
  { key: 14, labelKey: "overview.ranges.d14" },
];

export default function Overview() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [range, setRange] = useState(14);

  return (
    <PageFrame
      title={t("overview.title")}
      subtitle={t("overview.subtitle")}
      actions={
        <>
          <button
            type="button"
            onClick={() => navigate("/batch")}
            className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border border-background-300 px-3 py-2 text-xs text-foreground-700 transition-colors hover:border-background-400 hover:text-foreground-950"
          >
            <i className="ri-stack-line text-sm"></i>
            {t("overview.actions.batch")}
          </button>
          <button
            type="button"
            onClick={() => navigate("/search")}
            className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md bg-primary-500 px-3.5 py-2 text-xs font-medium text-background-50 transition-colors hover:bg-primary-600"
          >
            <i className="ri-add-line text-sm"></i>
            {t("overview.actions.newEval")}
          </button>
        </>
      }
    >
      <DemoBanner />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          icon="ri-global-line"
          label={t("overview.stats.covered")}
          value={overviewStats.coveredCompanies.toLocaleString()}
          delta={t("overview.stats.coveredDelta")}
          tone="primary"
          delay={0}
          to="/search"
        />
        <StatCard
          icon="ri-file-list-3-line"
          label={t("overview.stats.today")}
          value={overviewStats.todayEvaluations.toLocaleString()}
          delta={t("overview.stats.todayDelta")}
          tone="accent"
          delay={60}
        />
        <StatCard
          icon="ri-alert-line"
          label={t("overview.stats.highRisk")}
          value={overviewStats.highRiskCount.toLocaleString()}
          delta={t("overview.stats.highRiskDelta")}
          tone="secondary"
          delay={120}
        />
        <StatCard
          icon="ri-speed-up-line"
          label={t("overview.stats.avgScore")}
          value={String(overviewStats.avgCreditScore)}
          unit={t("overview.stats.avgScoreUnit")}
          delta={t("overview.stats.avgDelta")}
          tone="primary"
          delay={180}
        />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card
          className="lg:col-span-2"
          title={t("overview.chart.trendTitle")}
          subtitle={t("overview.chart.trendSubtitle")}
          icon="ri-line-chart-line"
          bodyClassName="px-2 pb-3 pt-4"
          action={
            <div className="flex items-center gap-1 rounded-full border border-background-200 bg-background-50 p-1">
              {RANGES.map((r) => (
                <button
                  key={r.key}
                  type="button"
                  onClick={() => setRange(r.key)}
                  className={`whitespace-nowrap rounded-full px-3 py-1 text-[11px] transition-colors cursor-pointer ${
                    range === r.key
                      ? "bg-primary-500 text-background-50"
                      : "text-foreground-500 hover:text-foreground-900"
                  }`}
                >
                  {t(r.labelKey)}
                </button>
              ))}
            </div>
          }
        >
          <EvaluationTrendChart range={range} />
        </Card>

        <Card
          title={t("overview.risk.title")}
          subtitle={t("overview.risk.subtitle")}
          icon="ri-pie-chart-2-line"
          bodyClassName="px-4 py-5"
        >
          <RiskDistributionChart />
        </Card>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card
          title={t("overview.system.title")}
          subtitle={t("overview.system.subtitle")}
          icon="ri-pulse-line"
          bodyClassName="py-0"
        >
          <SystemStatusPanel />
        </Card>

        <Card
          className="lg:col-span-2"
          title={t("overview.recent.title")}
          subtitle={t("overview.recent.subtitle")}
          icon="ri-history-line"
          bodyClassName="py-0"
          action={
            <button
              type="button"
              onClick={() => navigate("/search")}
              className="flex cursor-pointer items-center gap-1 whitespace-nowrap text-[11px] text-foreground-500 transition-colors hover:text-primary-400"
            >
              {t("overview.actions.viewAll")}
              <i className="ri-arrow-right-s-line text-sm"></i>
            </button>
          }
        >
          <RecentEvaluations />
        </Card>
      </div>

      <Card
        className="mt-4"
        title={t("overview.model.title")}
        subtitle={t("overview.model.subtitle")}
        icon="ri-cpu-line"
        bodyClassName="p-4"
        action={
          <button
            type="button"
            onClick={() => navigate("/model-card")}
            className="flex cursor-pointer items-center gap-1 whitespace-nowrap text-[11px] text-foreground-500 transition-colors hover:text-primary-400"
          >
            {t("overview.actions.modelCard")}
            <i className="ri-arrow-right-s-line text-sm"></i>
          </button>
        }
      >
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {modelMetrics.map((m) => (
            <div
              key={m.key}
              className="rounded-md border border-background-200 bg-background-50 p-3.5"
            >
              <p className="text-[11px] text-foreground-500">{m.label}</p>
              <p className="mt-1 font-mono text-xl font-semibold text-foreground-950">
                {m.value}
              </p>
              <p className="mt-1 text-[11px] text-accent-400">
                {t(`overview.model.metrics.${m.key}`)}
              </p>
            </div>
          ))}
        </div>
      </Card>
    </PageFrame>
  );
}