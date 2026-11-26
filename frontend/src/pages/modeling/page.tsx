import { useEffect } from "react";
import { Link, Navigate, useParams, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useModelingWorkbench } from "@/features/modeling/model/useModelingWorkbench";
import { WORKBENCH_SECTIONS, workbenchPath, type WorkbenchSection } from "@/features/modeling/model/workbenchSections";
import { box, button, secondary } from "./components/presentation";
import { CreateExperimentForm } from "./components/CreateExperimentForm";
import { DatasetImportPanel } from "./components/DatasetImportPanel";
import { DatasetPanel } from "./components/DatasetPanel";
import { EnterpriseDataPanel } from "./components/EnterpriseDataPanel";
import { ExperimentPanel } from "./components/ExperimentPanel";
import { ModelPanel } from "./components/ModelPanel";

export default function ModelingWorkbenchPage() {
  const { section } = useParams();
  const [params] = useSearchParams();
  const current = WORKBENCH_SECTIONS.find(({ id }) => id === section);
  if (!current) {
    const next = new URLSearchParams(params);
    const tab = next.get("tab");
    next.delete("tab");
    const destination = tab === "run" ? "experiments" : tab === "model" ? "models" : "datasets";
    return <Navigate to={{ pathname: workbenchPath(destination), search: next.toString() }} replace />;
  }

  return <Workbench section={current.id} />;
}

function Workbench({ section }: { section: WorkbenchSection }) {
  const { t } = useTranslation();
  const work = useModelingWorkbench();
  const [params] = useSearchParams();
  const toSection = (destination: WorkbenchSection) => ({
    pathname: workbenchPath(destination),
    search: params.toString(),
  });

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [section]);

  const datasetSection = section === "datasets" || section === "enterprise-data" || section === "new-experiment";
  const kind = datasetSection ? "dataset" : section === "experiments" ? "run" : null;
  const items = kind === "dataset" ? work.datasets : work.runs;
  const selectedId = kind === "dataset" ? work.datasetId : work.runId;
  const dataset = work.dataset;

  return (
    <div className="space-y-5 p-5 lg:p-8">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm text-foreground-500">{t("modeling.title")}</p>
          <h1 className="mt-1 font-heading text-2xl font-semibold text-foreground-950">
            {t(`modeling.sections.${section}`)}
          </h1>
        </div>
        <button
          className={secondary}
          onClick={() => void work.refresh()}
          disabled={work.busy}
        >
          {t("modeling.refresh")}
        </button>
      </header>

      <nav className="flex flex-wrap gap-2 lg:hidden" aria-label={t("modeling.title")}>
        {WORKBENCH_SECTIONS.map(({ id }) => (
          <Link key={id} to={toSection(id)} className={section === id ? button : secondary}
            aria-current={section === id ? "page" : undefined}>
            {t(`modeling.sections.${id}`)}
          </Link>
        ))}
      </nav>
      {work.error && (
        <div role="alert" className="rounded-lg border border-danger-500/30 p-3 text-sm text-danger-600">
          {work.error}
        </div>
      )}
      {work.loading && <p role="status">{t("modeling.loading")}</p>}
      {(section === "new-experiment" || section === "experiments") && (
        <p className="rounded-lg border border-accent-500/30 bg-accent-500/10 p-3 text-xs leading-relaxed text-foreground-700">
          {t("modeling.disclaimer")}
        </p>
      )}

      <div className={kind ? "grid gap-5 xl:grid-cols-[260px_minmax(0,1fr)]" : undefined}>
        {kind && (
          <aside className={`${box} space-y-3 self-start`}>
            <h2 className="font-semibold">{t(`modeling.tabs.${kind}`)}</h2>
            {kind === "dataset" && (
              <Link className="inline-block text-sm text-primary-500 underline" to={toSection("import")}>
                {t("modeling.sections.import")}
              </Link>
            )}
            <ul className="max-h-56 space-y-2 overflow-y-auto p-1 xl:max-h-[60vh]">
              {items.map((item) => (
                <li key={item.id}>
                  <button type="button" aria-pressed={selectedId === item.id}
                    onClick={() => work.select(kind, item.id, section)}
                    className={`block w-full rounded-md p-3 text-left ${selectedId === item.id ? "bg-primary-500/10 ring-1 ring-primary-400" : "bg-background-50"}`}>
                    <span className="block truncate text-sm font-medium">{item.name}</span>
                    <span className="mt-1 block font-mono text-[10px] text-foreground-500">
                      {t(`modeling.status.${item.status}`, { defaultValue: item.status })}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
            <p className="text-xs text-foreground-500">{t("modeling.scope")}</p>
          </aside>
        )}

        <div className="min-w-0 space-y-5">
          {datasetSection && !dataset && !work.loading && (
            <p className={`${box} text-sm text-foreground-500`}>
              {t(work.datasets.length ? "modeling.selectDataset" : "modeling.emptyDatasets")}
            </p>
          )}
          {section === "datasets" && dataset && (
            <>
              {dataset.status === "ready" && (
                <div className="flex flex-wrap gap-2">
                  <Link className={secondary} to={toSection("enterprise-data")}>
                    {t("modeling.sections.enterprise-data")}
                  </Link>
                  {dataset.supportedRunnerIds.includes("riskgnn") && (
                    <Link className={button} to={toSection("new-experiment")}>
                      {t("modeling.sections.new-experiment")}
                    </Link>
                  )}
                </div>
              )}
              <DatasetPanel work={work} dataset={dataset} />
            </>
          )}
          {section === "import" && <DatasetImportPanel work={work} />}
          {section === "enterprise-data" && dataset && (
            dataset.status === "ready" ? (
              <div className={box}>
                <h2 className="font-semibold">{dataset.name}</h2>
                <EnterpriseDataPanel key={dataset.id} work={work} />
              </div>
            ) : <p className={`${box} text-sm`}>{t("modeling.errors.notReady")}</p>
          )}
          {section === "new-experiment" && dataset && (
            <div className={`${box} space-y-3`}>
              <h2 className="font-semibold">{dataset.name}</h2>
              {dataset.status !== "ready" ? (
                <p className="text-sm">{t("modeling.errors.notReady")}</p>
              ) : dataset.supportedRunnerIds.includes("riskgnn") ? (
                <CreateExperimentForm key={dataset.id} work={work} />
              ) : <p className="text-sm text-foreground-500">{t("modeling.analysisOnly")}</p>}
            </div>
          )}
          {section === "experiments" && (
            <>
              <Link className={`${button} inline-block`} to={toSection("new-experiment")}>
                {t("modeling.sections.new-experiment")}
              </Link>
              <ExperimentPanel work={work} />
            </>
          )}
          {section === "models" && <ModelPanel work={work} />}
        </div>
      </div>
    </div>
  );
}
