import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { manifestOf, type ModelingDataset } from "@/entities/modeling/model/types";
import type { RunInput } from "@/features/modeling/model/useModelingWorkbench";
import Card from "@/shared/ui/Card";

interface ExperimentBuilderProps {
  dataset: ModelingDataset;
  queueing: boolean;
  onRun: (input: RunInput) => Promise<boolean>;
  onQueued?: () => void;
}

type ModelName = RunInput["models"][number];
const MODEL_NAMES: ModelName[] = [
  "logistic_regression",
  "hist_gradient_boosting",
  "graph_stats_hgb",
  "gnn_self_only",
  "gnn_no_hyper",
  "gnn_full",
];

export default function ExperimentBuilder({ dataset, queueing, onRun, onQueued }: ExperimentBuilderProps) {
  const { t } = useTranslation();
  const manifest = manifestOf(dataset);
  const features = useMemo(() => manifest?.features ?? [], [manifest]);
  const capabilities = dataset.capabilities;
  const [name, setName] = useState("");
  const [featureMode, setFeatureMode] = useState<"recommended" | "manual">("recommended");
  const [selectedFeatures, setSelectedFeatures] = useState<string[]>([]);
  const [models, setModels] = useState<ModelName[]>([]);
  const [seed, setSeed] = useState(42);
  const [useEvents, setUseEvents] = useState(true);
  const [useRelations, setUseRelations] = useState(true);
  const [useHyperedges, setUseHyperedges] = useState(true);

  const available = (model: ModelName) => {
    if (model === "graph_stats_hgb") return Boolean(capabilities.relations);
    if (model === "gnn_self_only" || model === "gnn_no_hyper") return Boolean(capabilities.gnn);
    if (model === "gnn_full") return Boolean(capabilities.gnn && capabilities.hyperedges);
    return true;
  };

  useEffect(() => {
    setName(`${dataset.name} comparison`);
    setSelectedFeatures(features.filter((item) => item.recommended !== false).map((item) => item.name));
    setModels(MODEL_NAMES.filter(available));
    setUseEvents(Boolean(capabilities.events));
    setUseRelations(Boolean(capabilities.relations));
    setUseHyperedges(Boolean(capabilities.hyperedges));
  // Dataset capabilities intentionally reset all dependent experiment controls.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataset.id, features]);

  if (!manifest) return null;
  const toggleModel = (model: ModelName) => setModels((current) => current.includes(model) ? current.filter((item) => item !== model) : [...current, model]);
  const toggleFeature = (feature: string) => setSelectedFeatures((current) => current.includes(feature) ? current.filter((item) => item !== feature) : [...current, feature]);
  const disabledReason = (model: ModelName) => {
    if (available(model)) return "";
    if (model === "gnn_full" && !capabilities.hyperedges) return t("modeling.builder.requiresHyper");
    return t("modeling.builder.requiresGraph");
  };

  return (
    <Card title={t("modeling.builder.title")} subtitle={t("modeling.builder.subtitle")} icon="ri-settings-3-line" bodyClassName="p-5">
      <div className="space-y-6">
        <div className="grid gap-4 md:grid-cols-3">
          <label className="text-xs font-medium text-foreground-700">{t("modeling.builder.name")}<input value={name} maxLength={128} onChange={(event) => setName(event.target.value)} className="mt-1.5 w-full rounded-md border border-background-300 bg-background-50 px-3 py-2 text-sm outline-none focus:border-primary-400" /></label>
          <label className="text-xs font-medium text-foreground-700">{t("modeling.builder.target")}<input value={manifest.target.name} disabled className="mt-1.5 w-full rounded-md border border-background-300 bg-background-100 px-3 py-2 font-mono text-sm text-foreground-600" /></label>
          <label className="text-xs font-medium text-foreground-700">{t("modeling.builder.seed")}<input type="number" min={0} value={seed} onChange={(event) => setSeed(Number(event.target.value))} className="mt-1.5 w-full rounded-md border border-background-300 bg-background-50 px-3 py-2 text-sm" /></label>
        </div>

        <div>
          <p className="text-xs font-medium text-foreground-700">{t("modeling.builder.featureMode")}</p>
          <div className="mt-2 flex gap-2">{(["recommended", "manual"] as const).map((mode) => <button key={mode} type="button" onClick={() => setFeatureMode(mode)} className={`rounded-md border px-3 py-2 text-xs ${featureMode === mode ? "border-primary-500 bg-primary-500/10 text-primary-400" : "border-background-200 text-foreground-600"}`}>{t(`modeling.builder.${mode}`)}</button>)}</div>
          {featureMode === "manual" && <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{features.map((feature) => <label key={feature.name} className="flex items-center gap-2 rounded-md border border-background-200 px-3 py-2 text-xs"><input type="checkbox" checked={selectedFeatures.includes(feature.name)} onChange={() => toggleFeature(feature.name)} className="accent-primary-500" /><span className="truncate font-mono">{feature.name}</span><span className="ml-auto text-foreground-400">{feature.group}</span></label>)}</div>}
        </div>

        <div>
          <p className="text-xs font-medium text-foreground-700">{t("modeling.builder.models")}</p>
          <div className="mt-2 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {MODEL_NAMES.map((model) => <label key={model} title={disabledReason(model)} className={`rounded-md border px-3 py-3 text-xs ${available(model) ? "cursor-pointer border-background-200" : "cursor-not-allowed border-background-200 opacity-45"}`}><span className="flex items-center gap-2"><input type="checkbox" disabled={!available(model)} checked={models.includes(model)} onChange={() => toggleModel(model)} className="accent-primary-500" /><b className="font-mono text-foreground-900">{model}</b></span>{!available(model) && <span className="mt-1 block text-warning-600">{disabledReason(model)}</span>}</label>)}
          </div>
        </div>

        <div className="flex flex-wrap gap-4 rounded-md bg-background-50 p-3 text-xs text-foreground-700">
          <label><input type="checkbox" disabled={!capabilities.events} checked={useEvents} onChange={(event) => setUseEvents(event.target.checked)} className="mr-2 accent-primary-500" />{t("modeling.builder.events")}</label>
          <label><input type="checkbox" disabled={!capabilities.relations} checked={useRelations} onChange={(event) => { const checked = event.target.checked; setUseRelations(checked); if (!checked) setModels((current) => current.filter((model) => !["graph_stats_hgb", "gnn_no_hyper", "gnn_full"].includes(model))); }} className="mr-2 accent-primary-500" />{t("modeling.builder.relations")}</label>
          <label><input type="checkbox" disabled={!capabilities.hyperedges} checked={useHyperedges} onChange={(event) => { const checked = event.target.checked; setUseHyperedges(checked); if (!checked) setModels((current) => current.filter((model) => model !== "gnn_full")); }} className="mr-2 accent-primary-500" />{t("modeling.builder.hyperedges")}</label>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-background-200 pt-4">
          <p className="max-w-2xl text-xs leading-relaxed text-foreground-500">{t("modeling.builder.method")}</p>
          <button type="button" disabled={queueing || !name.trim() || models.length === 0 || (featureMode === "manual" && selectedFeatures.length === 0)} onClick={() => void onRun({ datasetId: dataset.id, name: name.trim(), targetName: manifest.target.name, featureMode, featureColumns: featureMode === "manual" ? selectedFeatures : [], models, useEvents, useRelations, useHyperedges, enableGnnAblations: models.some((model) => model.startsWith("gnn_")), seed }).then((queued) => { if (queued) onQueued?.(); })} className="rounded-md bg-primary-500 px-5 py-2.5 text-sm font-medium text-white hover:bg-primary-600 disabled:cursor-not-allowed disabled:opacity-40">{queueing ? t("modeling.builder.queueing") : t("modeling.builder.run")}</button>
        </div>
      </div>
    </Card>
  );
}
