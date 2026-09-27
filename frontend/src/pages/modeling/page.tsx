import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useModelingWorkbench } from "@/features/modeling/model/useModelingWorkbench";
import DatasetAnalysisPanel from "@/pages/modeling/components/DatasetAnalysisPanel";
import DatasetBundlePanel from "@/pages/modeling/components/DatasetBundlePanel";
import ExperimentBuilder from "@/pages/modeling/components/ExperimentBuilder";
import ExperimentResult from "@/pages/modeling/components/ExperimentResult";
import UploadPanel from "@/pages/modeling/components/UploadPanel";

type Stage = "data" | "quality" | "build" | "evaluate";
const stages: Stage[] = ["data", "quality", "build", "evaluate"];

export default function ModelingWorkbenchPage() {
  const { t } = useTranslation();
  const workbench = useModelingWorkbench();
  const [stage, setStage] = useState<Stage>("data");

  useEffect(() => {
    if (!workbench.selectedDataset) setStage("data");
  }, [workbench.selectedDataset]);

  const canOpen = (next: Stage) => {
    if (next === "data") return true;
    if (next === "quality" || next === "build") return workbench.selectedDataset?.status === "ready";
    return Boolean(workbench.selectedExperiment);
  };

  return (
    <div className="mx-auto max-w-[1500px] space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-primary-400">{t("modeling.eyebrow")}</p>
          <h1 className="mt-1 font-heading text-2xl font-semibold text-foreground-950 md:text-3xl">{t("modeling.title")}</h1>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-foreground-500">{t("modeling.subtitle")}</p>
        </div>
        <div className="flex rounded-lg border border-background-200 bg-background-100 p-1 text-[11px]">
          {stages.map((item, index) => <button key={item} type="button" disabled={!canOpen(item)} onClick={() => setStage(item)} className={`flex items-center gap-1.5 rounded-md px-3 py-2 ${stage === item ? "bg-primary-500 text-white" : "text-foreground-500 disabled:opacity-35"}`}><b className="font-mono">0{index + 1}</b>{t(`modeling.steps.${item}`)}</button>)}
        </div>
      </header>

      {workbench.error && <div role="alert" className="flex items-center justify-between rounded-lg border border-danger-500/30 bg-danger-500/8 px-4 py-3 text-sm text-danger-600"><span>{workbench.error}</span><button type="button" className="text-xs underline" onClick={() => void workbench.load()}>{t("modeling.retry")}</button></div>}

      <div className="grid gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
        <aside className="space-y-4">
          <UploadPanel busy={workbench.busy} onUpload={async (file, name) => { await workbench.upload(file, name); setStage("data"); }} />
          <section className="rounded-lg border border-background-200 bg-background-100 p-3">
            <h2 className="px-1 text-sm font-semibold text-foreground-900">{t("modeling.datasets")}</h2>
            <div className="mt-2 space-y-1">
              {workbench.loading && <p className="px-2 py-4 text-xs text-foreground-500">{t("modeling.loading")}</p>}
              {!workbench.loading && workbench.datasets.length === 0 && <p className="px-2 py-4 text-xs leading-relaxed text-foreground-500">{t("modeling.empty")}</p>}
              {workbench.datasets.map((dataset) => <button type="button" key={dataset.id} onClick={() => { workbench.selectDataset(dataset); setStage("data"); }} className={`w-full rounded-md px-3 py-2.5 text-left transition ${workbench.selectedDataset?.id === dataset.id ? "bg-primary-500/12" : "hover:bg-background-50"}`}><span className="block truncate text-sm font-medium text-foreground-900">{dataset.name}</span><span className="mt-1 flex justify-between font-mono text-[10px] text-foreground-500"><span>{t(`modeling.status.${dataset.status}`)}</span><span>{dataset.rowCount ? `${dataset.rowCount} × ${dataset.columnCount}` : `${dataset.progress.percent ?? 0}%`}</span></span></button>)}
            </div>
          </section>
          {workbench.experiments.length > 0 && <section className="rounded-lg border border-background-200 bg-background-100 p-3"><h2 className="px-1 text-sm font-semibold text-foreground-900">{t("modeling.experiments")}</h2><div className="mt-2 space-y-1">{workbench.experiments.map((experiment) => <button type="button" key={experiment.id} onClick={() => { workbench.selectExperiment(experiment); setStage("evaluate"); }} className={`w-full rounded-md px-3 py-2.5 text-left transition ${workbench.selectedExperiment?.id === experiment.id ? "bg-primary-500/12" : "hover:bg-background-50"}`}><span className="block truncate text-sm font-medium text-foreground-900">{experiment.name}</span><span className="mt-1 flex justify-between font-mono text-[10px] text-foreground-500"><span>{t(`modeling.status.${experiment.status}`)}</span><span>{experiment.requestedModels.length} models</span></span></button>)}</div></section>}
        </aside>

        <main className="min-w-0 space-y-5">
          {!workbench.selectedDataset ? <div className="flex min-h-[420px] flex-col items-center justify-center rounded-lg border border-dashed border-background-300 bg-background-100 text-center"><i className="ri-database-2-line text-4xl text-foreground-400" /><h2 className="mt-3 text-lg font-semibold text-foreground-900">{t("modeling.welcome.title")}</h2><p className="mt-2 max-w-md text-sm text-foreground-500">{t("modeling.welcome.subtitle")}</p></div> : (
            <>
              {stage === "data" && <DatasetBundlePanel dataset={workbench.selectedDataset} />}
              {stage === "quality" && workbench.selectedDataset.status === "ready" && <DatasetAnalysisPanel dataset={workbench.selectedDataset} />}
              {stage === "build" && workbench.selectedDataset.status === "ready" && <ExperimentBuilder dataset={workbench.selectedDataset} queueing={workbench.busy === "queueing"} onRun={workbench.run} onQueued={() => setStage("evaluate")} />}
              {stage === "evaluate" && workbench.selectedExperiment && <ExperimentResult experiment={workbench.selectedExperiment} />}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
