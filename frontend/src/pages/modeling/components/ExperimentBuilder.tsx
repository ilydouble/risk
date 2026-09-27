import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import type { ModelingDataset } from "@/entities/modeling/model/types";
import Card from "@/shared/ui/Card";

interface ExperimentBuilderProps {
  dataset: ModelingDataset;
  training: boolean;
  onRun: (input: {
    datasetId: string;
    name: string;
    targetColumn: string;
    positiveValue: string;
    featureColumns: string[];
    seed: number;
  }) => Promise<void>;
}

export default function ExperimentBuilder({ dataset, training, onRun }: ExperimentBuilderProps) {
  const { t } = useTranslation();
  const candidates = useMemo(() => dataset.analysis?.targetCandidates ?? [], [dataset.analysis]);
  const numeric = useMemo(
    () => dataset.analysis?.columns.filter((column) => column.kind === "numeric") ?? [],
    [dataset.analysis],
  );
  const [target, setTarget] = useState("");
  const [positive, setPositive] = useState("");
  const [features, setFeatures] = useState<string[]>([]);
  const [name, setName] = useState("");

  useEffect(() => {
    const nextTarget = candidates[0]?.name ?? "";
    setTarget(nextTarget);
    setPositive(candidates[0]?.values[1] ?? "");
    setFeatures(
      numeric
        .map((column) => column.name)
        .filter((column) => column !== nextTarget)
        .slice(0, 12),
    );
    setName(`${dataset.name} baseline`);
  }, [candidates, dataset.id, dataset.name, numeric]);

  const targetValues = candidates.find((candidate) => candidate.name === target)?.values ?? [];
  const toggle = (column: string) => {
    setFeatures((current) =>
      current.includes(column)
        ? current.filter((item) => item !== column)
        : current.length < 20
          ? [...current, column]
          : current,
    );
  };

  return (
    <Card
      title={t("modeling.builder.title")}
      subtitle={t("modeling.builder.subtitle")}
      icon="ri-settings-3-line"
      bodyClassName="p-5"
    >
      {candidates.length === 0 ? (
        <p className="rounded-md border border-danger-500/30 bg-danger-500/8 px-4 py-3 text-sm text-danger-600">
          {t("modeling.builder.noTarget")}
        </p>
      ) : (
        <div className="space-y-5">
          <div className="grid gap-4 md:grid-cols-3">
            <label className="text-xs font-medium text-foreground-700">
              {t("modeling.builder.name")}
              <input
                value={name}
                maxLength={128}
                onChange={(event) => setName(event.target.value)}
                className="mt-1.5 w-full rounded-md border border-background-300 bg-background-50 px-3 py-2 text-sm outline-none focus:border-primary-400"
              />
            </label>
            <label className="text-xs font-medium text-foreground-700">
              {t("modeling.builder.target")}
              <select
                value={target}
                onChange={(event) => {
                  const next = event.target.value;
                  setTarget(next);
                  setPositive(candidates.find((item) => item.name === next)?.values[1] ?? "");
                  setFeatures((items) => items.filter((item) => item !== next));
                }}
                className="mt-1.5 w-full rounded-md border border-background-300 bg-background-50 px-3 py-2 text-sm outline-none focus:border-primary-400"
              >
                {candidates.map((candidate) => (
                  <option key={candidate.name} value={candidate.name}>{candidate.name}</option>
                ))}
              </select>
            </label>
            <label className="text-xs font-medium text-foreground-700">
              {t("modeling.builder.positive")}
              <select
                value={positive}
                onChange={(event) => setPositive(event.target.value)}
                className="mt-1.5 w-full rounded-md border border-background-300 bg-background-50 px-3 py-2 text-sm outline-none focus:border-primary-400"
              >
                {targetValues.map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </label>
          </div>

          <div>
            <div className="flex items-center justify-between">
              <p className="text-xs font-medium text-foreground-700">{t("modeling.builder.features")}</p>
              <span className="font-mono text-[11px] text-foreground-500">{features.length}/20</span>
            </div>
            <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {numeric.filter((column) => column.name !== target).map((column) => (
                <label key={column.name} className="flex cursor-pointer items-center gap-2 rounded-md border border-background-200 bg-background-50 px-3 py-2 text-xs text-foreground-700">
                  <input
                    type="checkbox"
                    checked={features.includes(column.name)}
                    onChange={() => toggle(column.name)}
                    className="accent-primary-500"
                  />
                  <span className="truncate font-mono">{column.name}</span>
                  {column.missingRate > 0 && (
                    <span className="ml-auto text-warning-600">
                      {(column.missingRate * 100).toFixed(0)}%
                    </span>
                  )}
                </label>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-background-200 pt-4">
            <p className="max-w-xl text-xs leading-relaxed text-foreground-500">
              {t("modeling.builder.method")}
            </p>
            <button
              type="button"
              disabled={training || !name.trim() || !target || !positive || features.length === 0}
              onClick={() => void onRun({
                datasetId: dataset.id,
                name: name.trim(),
                targetColumn: target,
                positiveValue: positive,
                featureColumns: features,
                seed: 42,
              })}
              className="rounded-md bg-primary-500 px-5 py-2.5 text-sm font-medium text-white hover:bg-primary-600 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {training ? t("modeling.builder.training") : t("modeling.builder.run")}
            </button>
          </div>
        </div>
      )}
    </Card>
  );
}
