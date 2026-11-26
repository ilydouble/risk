import { useTranslation } from "react-i18next";
import { DatasetClearButton } from "@/features/modeling/ui/DatasetClearButton";
import type { useModelingWorkbench } from "@/features/modeling/model/useModelingWorkbench";
import { DatasetAnalysisPanel } from "./DatasetAnalysisPanel";
import { box } from "./presentation";

type Workbench = ReturnType<typeof useModelingWorkbench>;

export function DatasetPanel({ work, dataset }: { work: Workbench; dataset: NonNullable<Workbench["dataset"]> }) {
  const { t } = useTranslation();
  const stage = (value: string) =>
    t(`modeling.status.${value}`, { defaultValue: value });

  return (
    <section className={`${box} space-y-4`}>
      <div className="flex flex-wrap justify-between gap-2">
        <h2 className="font-semibold">{dataset.name}</h2>
        <span className="text-sm text-primary-500">
          {stage(dataset.status)} · {stage(dataset.stage)}
        </span>
      </div>
      <DatasetClearButton key={dataset.id} dataset={dataset} disabled={work.busy} onCleared={work.datasetCleared} />
      {dataset.error && (
        <pre className="overflow-auto whitespace-pre-wrap text-xs text-danger-500">
          {dataset.error}
        </pre>
      )}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {Object.entries(dataset.counts).map(([key, value]) => (
          <div key={key} className="rounded-md bg-background-50 p-3">
            <span className="block truncate text-xs text-foreground-500">
              {key}
            </span>
            <strong className="font-mono">{value.toLocaleString()}</strong>
          </div>
        ))}
      </div>
      {dataset.sha256 && (
        <p className="break-all font-mono text-[10px] text-foreground-500">
          SHA-256 {dataset.sha256}
        </p>
      )}
      <details>
        <summary className="cursor-pointer text-sm">
          {t("modeling.upload.verifiedFiles")} ({dataset.files.length})
        </summary>
        <div className="max-h-48 overflow-auto text-xs">
          {dataset.files.map((entry) => (
            <div
              key={entry.path}
              className="border-b border-background-200 py-2"
            >
              <p>{entry.path}</p>
              <p className="break-all font-mono text-[10px] text-foreground-500">
                {entry.sha256}
              </p>
            </div>
          ))}
        </div>
      </details>
      <p className="text-xs text-foreground-500">
        {t("modeling.dataFormat")}: {dataset.dataFormat ?? "—"}
      </p>
      {dataset.datasetIdentity && (
        <p className="text-xs text-foreground-500">
          {t("modeling.contractIdentity")}: {dataset.datasetIdentity} / {dataset.datasetVersion}
          {" · "}{t("modeling.adapter")}: {dataset.adapterId} / {dataset.adapterVersion}
        </p>
      )}
      <DatasetAnalysisPanel dataset={dataset} />
      {dataset.sourcePreparationId && <p className="text-sm text-foreground-500">来源准备记录：{dataset.sourcePreparationId} · 已封存原始文件摘要与确认映射，后续编辑不会改写此训练包的来源快照。</p>}
    </section>
  );
}
