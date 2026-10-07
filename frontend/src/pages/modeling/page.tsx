import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useModelingWorkbench } from "@/features/modeling/model/useModelingWorkbench";
import { box, button, secondary } from "./components/presentation";
import { DatasetPanel } from "./components/DatasetPanel";
import { ExperimentPanel } from "./components/ExperimentPanel";
import { ModelPanel } from "./components/ModelPanel";
export default function ModelingWorkbenchPage() {
  const { t } = useTranslation();
  const work = useModelingWorkbench();
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") ?? "dataset";
  const stage = (value: string) =>
    t(`modeling.status.${value}`, { defaultValue: value });

  return (
    <div className="space-y-5 p-5 lg:p-8">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="font-mono text-xs uppercase tracking-widest text-primary-500">
            Model workbench
          </p>
          <h1 className="mt-2 font-heading text-2xl font-semibold text-foreground-950">
            {t("modeling.title")}
          </h1>
          <p className="mt-2 text-sm text-foreground-500">
            {t("modeling.subtitle")}
          </p>
        </div>
        <button
          className={secondary}
          onClick={() => void work.refresh()}
          disabled={work.busy}
        >
          {t("modeling.refresh")}
        </button>
      </header>
      <div className="rounded-lg border border-accent-500/30 bg-accent-500/10 p-3 text-xs leading-relaxed text-foreground-700">
        {t("modeling.disclaimer")}
      </div>
      {work.error && (
        <div
          role="alert"
          className="rounded-lg border border-danger-500/30 p-3 text-sm text-danger-600"
        >
          {work.error}
        </div>
      )}
      <nav className="flex gap-2" aria-label={t("modeling.title")}>
        {["dataset", "run", "model"].map((key, index) => (
          <button
            key={key}
            className={tab === key ? button : secondary}
            onClick={() =>
              setParams((previous) => {
                const next = new URLSearchParams(previous);
                next.set("tab", key);
                return next;
              })
            }
          >
            {index + 1}. {t(`modeling.tabs.${key}`)}
          </button>
        ))}
      </nav>
      {work.loading && <p role="status">{t("modeling.loading")}</p>}
      <div className="grid gap-5 xl:grid-cols-[280px_minmax(0,1fr)]">
        <aside className={`${box} space-y-4 self-start`}>
          <h2 className="font-semibold">{t(`modeling.tabs.${tab}`)}</h2>
          {(tab === "dataset"
            ? work.datasets
            : tab === "run"
              ? work.runs
              : work.models
          ).map((item) => (
            <button
              key={item.id}
              onClick={() => work.select(tab, item.id)}
              className={`block w-full rounded-md p-3 text-left ${[work.datasetId, work.runId, work.modelId].includes(item.id) ? "bg-primary-500/10 ring-1 ring-primary-400" : "bg-background-50"}`}
            >
              <span className="block truncate text-sm font-medium">
                {item.name}
              </span>
              <span className="mt-1 block font-mono text-[10px] text-foreground-500">
                {"status" in item ? stage(item.status) : item.id.slice(0, 8)}
              </span>
            </button>
          ))}
          <p className="text-xs text-foreground-500">{t("modeling.scope")}</p>
        </aside>
        <main className="min-w-0 space-y-5">
          {tab === "dataset" && <DatasetPanel work={work} />}
          {tab === "run" && <ExperimentPanel work={work} />}
          {tab === "model" && <ModelPanel work={work} />}
        </main>
      </div>
    </div>
  );
}
