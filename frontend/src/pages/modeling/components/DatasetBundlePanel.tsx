import { useTranslation } from "react-i18next";
import { manifestOf, type ModelingDataset } from "@/entities/modeling/model/types";
import Card from "@/shared/ui/Card";

interface DatasetBundlePanelProps {
  dataset: ModelingDataset;
}

export default function DatasetBundlePanel({ dataset }: DatasetBundlePanelProps) {
  const { t } = useTranslation();
  const manifest = manifestOf(dataset);
  const files = manifest
    ? Object.entries(manifest.files).filter((entry): entry is [string, NonNullable<typeof entry[1]>] => Boolean(entry[1]))
    : [];
  const progress = Number(dataset.progress.percent ?? 0);

  return (
    <div className="space-y-4">
      <Card title={t("modeling.bundle.title")} icon="ri-archive-stack-line" bodyClassName="p-5">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            [t("modeling.bundle.schema"), manifest ? `Bundle v${manifest.schemaVersion}` : "—"],
            [t("modeling.bundle.task"), dataset.taskType ? t(`modeling.task.${dataset.taskType}`) : "—"],
            [t("modeling.bundle.status"), t(`modeling.status.${dataset.status}`)],
            [t("modeling.bundle.rows"), dataset.rowCount?.toLocaleString() ?? "—"],
          ].map(([label, value]) => (
            <div key={label} className="rounded-lg border border-background-200 bg-background-50 p-4">
              <p className="text-xs text-foreground-500">{label}</p>
              <p className="mt-1 text-sm font-semibold text-foreground-900">{value}</p>
            </div>
          ))}
        </div>
        {dataset.status !== "ready" && dataset.status !== "legacy" && (
          <div className="mt-5">
            <div className="mb-1.5 flex justify-between text-xs text-foreground-500">
              <span>{String(dataset.progress.stage ?? dataset.status)}</span>
              <span>{progress}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-background-200">
              <div className="h-full bg-primary-500 transition-all" style={{ width: `${progress}%` }} />
            </div>
          </div>
        )}
        {dataset.error && (
          <p className="mt-4 rounded-md border border-danger-500/30 bg-danger-500/8 px-4 py-3 text-xs text-danger-600">
            {dataset.error}
          </p>
        )}
      </Card>

      {manifest && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title={t("modeling.bundle.target")} icon="ri-focus-3-line" bodyClassName="p-5">
            <p className="font-mono text-sm text-primary-400">{manifest.target.name}</p>
            <p className="mt-2 text-sm leading-relaxed text-foreground-700">
              {manifest.target.businessDefinition}
            </p>
            <dl className="mt-4 grid grid-cols-2 gap-3 text-xs">
              <div><dt className="text-foreground-500">{t("modeling.bundle.positive")}</dt><dd className="mt-1 font-mono text-foreground-900">{String(manifest.target.positiveValue)}</dd></div>
              <div><dt className="text-foreground-500">{t("modeling.bundle.window")}</dt><dd className="mt-1 font-mono text-foreground-900">{manifest.target.predictionWindowDays ? `${manifest.target.predictionWindowDays} d` : "—"}</dd></div>
            </dl>
          </Card>
          <Card title={t("modeling.bundle.files")} icon="ri-file-list-3-line" bodyClassName="p-5">
            <div className="space-y-2">
              {files.map(([name, file]) => (
                <div key={name} className="flex items-center justify-between rounded-md border border-background-200 px-3 py-2 text-xs">
                  <span><b className="font-mono text-foreground-900">{name}</b><span className="ml-2 text-foreground-500">{file.path}</span></span>
                  <span className="font-mono text-foreground-500">{file.format.toUpperCase()}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {manifest?.graph?.staticExperimentOnly && (
        <p className="rounded-md border border-warning-500/30 bg-warning-500/8 px-4 py-3 text-xs text-warning-700">
          {t("modeling.bundle.staticWarning")}
        </p>
      )}
    </div>
  );
}
