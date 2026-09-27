import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import PageFrame from "@/features/workbench-layout/ui/PageFrame";
import Card from "@/shared/ui/Card";
import StatCard from "@/shared/ui/StatCard";
import AgeDistributionChart from "@/pages/overview/components/AgeDistributionChart";
import DataQuality from "@/pages/overview/components/DataQuality";
import DatasetBanner from "@/pages/overview/components/DatasetBanner";
import GraphComponents from "@/pages/overview/components/GraphComponents";
import LabelDistributionChart from "@/pages/overview/components/LabelDistributionChart";
import SampleCompanies from "@/pages/overview/components/SampleCompanies";
import { useOverview } from "@/pages/overview/model/useOverview";

export default function Overview() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { data, loading, error, retry } = useOverview();

  return (
    <PageFrame
      title={t("overview.title")}
      subtitle={t("overview.subtitle")}
      actions={
        <>
          <button
            type="button"
            onClick={() => navigate("/benchmark")}
            className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border border-background-300 px-3 py-2 text-xs text-foreground-700 transition-colors hover:border-background-400 hover:text-foreground-950"
          >
            <i className="ri-flask-line text-sm" />
            {t("overview.actions.benchmark")}
          </button>
          <button
            type="button"
            onClick={() => navigate("/modeling")}
            className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md bg-primary-500 px-3.5 py-2 text-xs font-medium text-background-50 transition-colors hover:bg-primary-600"
          >
            <i className="ri-brain-line text-sm" />
            {t("overview.actions.modeling")}
          </button>
        </>
      }
    >
      {loading && (
        <p role="status" className="rounded-lg border border-background-200 bg-background-100 p-8 text-sm text-foreground-600">
          {t("overview.loading")}
        </p>
      )}

      {!loading && error && (
        <div role="alert" className="flex items-center justify-between gap-4 rounded-lg border border-danger-500/30 bg-danger-500/8 px-4 py-3 text-sm text-danger-600">
          <span>{error}</span>
          <button type="button" className="text-xs underline" onClick={retry}>
            {t("overview.retry")}
          </button>
        </div>
      )}

      {!loading && data && (
        <>
          <DatasetBanner dataset={data.dataset} />

          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard icon="ri-building-2-line" label={t("overview.stats.companies")} value={data.stats.companyCount.toLocaleString()} delta={t("overview.stats.fullAggregate")} tone="primary" />
            <StatCard icon="ri-price-tag-3-line" label={t("overview.stats.labeled")} value={data.stats.labeledCount.toLocaleString()} delta={`${(data.quality.labeledRate * 100).toFixed(1)}%`} tone="accent" delay={60} />
            <StatCard icon="ri-alarm-warning-line" label={t("overview.stats.distress")} value={data.stats.distressCount.toLocaleString()} delta={t("overview.stats.entityLabel")} tone="secondary" delay={120} />
            <StatCard icon="ri-share-line" label={t("overview.stats.edges")} value={data.stats.edgeCount.toLocaleString()} delta={t("overview.stats.edgeCoverage", { value: (data.quality.ordinaryEdgeCoverageWithinLabeled * 100).toFixed(2) })} tone="primary" delay={180} />
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
            <Card className="lg:col-span-2" title={t("overview.age.title")} subtitle={t("overview.age.subtitle")} icon="ri-bar-chart-grouped-line" bodyClassName="px-2 pb-3 pt-4">
              <AgeDistributionChart data={data.ageDistribution} />
            </Card>
            <Card title={t("overview.labels.title")} subtitle={t("overview.labels.subtitle")} icon="ri-pie-chart-2-line" bodyClassName="px-4 py-5">
              <LabelDistributionChart data={data.labelDistribution} />
            </Card>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
            <Card className="lg:col-span-2" title={t("overview.quality.title")} subtitle={t("overview.quality.subtitle")} icon="ri-shield-check-line" bodyClassName="p-0">
              <DataQuality quality={data.quality} />
            </Card>
            <Card title={t("overview.graph.title")} subtitle={t("overview.graph.subtitle")} icon="ri-node-tree" bodyClassName="p-0">
              <GraphComponents components={data.graphComponents} edgeTypes={data.edgeTypes} />
            </Card>
          </div>

          <Card className="mt-4" title={t("overview.samples.title")} subtitle={t("overview.samples.subtitle", { count: data.sampling.sampleCount })} icon="ri-table-line" bodyClassName="p-0">
            <SampleCompanies samples={data.sampleCompanies} />
          </Card>

          <Card className="mt-4" title={t("overview.warnings.title")} icon="ri-error-warning-line" bodyClassName="p-4">
            <ul className="space-y-2 text-xs leading-relaxed text-foreground-600">
              {data.warnings.map((warning) => (
                <li key={warning} className="flex gap-2">
                  <i className="ri-information-line mt-0.5 text-accent-400" />
                  <span>{t(`overview.warnings.${warning}`)}</span>
                </li>
              ))}
            </ul>
          </Card>
        </>
      )}
    </PageFrame>
  );
}
