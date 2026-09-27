import { useTranslation } from "react-i18next";
import type { ModelingDataset } from "@/entities/modeling/model/types";
import Card from "@/shared/ui/Card";

interface DatasetAnalysisPanelProps {
  dataset: ModelingDataset;
}

function percent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

export default function DatasetAnalysisPanel({ dataset }: DatasetAnalysisPanelProps) {
  const { t } = useTranslation();
  const analysis = dataset.analysis;
  if (!analysis) return null;
  const previewColumns = analysis.columns.slice(0, 8);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[
          [t("modeling.analysis.rows"), analysis.rowCount.toLocaleString()],
          [t("modeling.analysis.columns"), String(analysis.columnCount)],
          [t("modeling.analysis.missing"), percent(analysis.missingRate)],
          [t("modeling.analysis.duplicates"), String(analysis.duplicateRows)],
        ].map(([label, value]) => (
          <div key={label} className="rounded-lg border border-background-200 bg-background-100 p-4">
            <p className="text-xs text-foreground-500">{label}</p>
            <p className="mt-1 font-heading text-2xl font-semibold text-foreground-950">{value}</p>
          </div>
        ))}
      </div>

      {analysis.warnings.length > 0 && (
        <div className="rounded-lg border border-warning-500/30 bg-warning-500/8 px-4 py-3 text-xs text-warning-700">
          {analysis.warnings.map((warning) => t(`modeling.warnings.${warning}`)).join(" · ")}
        </div>
      )}

      <Card title={t("modeling.analysis.fields")} icon="ri-table-line" bodyClassName="overflow-x-auto">
        <table className="w-full min-w-[680px] text-left text-xs">
          <thead className="border-b border-background-200 bg-background-50 text-foreground-500">
            <tr>
              <th className="px-4 py-2.5 font-medium">{t("modeling.analysis.field")}</th>
              <th className="px-4 py-2.5 font-medium">{t("modeling.analysis.type")}</th>
              <th className="px-4 py-2.5 font-medium">{t("modeling.analysis.missing")}</th>
              <th className="px-4 py-2.5 font-medium">{t("modeling.analysis.unique")}</th>
              <th className="px-4 py-2.5 font-medium">{t("modeling.analysis.sample")}</th>
            </tr>
          </thead>
          <tbody>
            {analysis.columns.map((column) => (
              <tr key={column.name} className="border-b border-background-200/60 last:border-0">
                <td className="px-4 py-3 font-mono text-foreground-900">{column.name}</td>
                <td className="px-4 py-3 text-foreground-700">
                  {t(`modeling.types.${column.kind}`)}
                </td>
                <td className="px-4 py-3 text-foreground-700">{percent(column.missingRate)}</td>
                <td className="px-4 py-3 text-foreground-700">{column.uniqueCount}</td>
                <td className="max-w-64 truncate px-4 py-3 text-foreground-500">
                  {column.samples.join(" / ") || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      {dataset.preview && dataset.preview.length > 0 && (
        <Card title={t("modeling.analysis.preview")} icon="ri-eye-line" bodyClassName="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-xs">
            <thead className="border-b border-background-200 bg-background-50 text-foreground-500">
              <tr>
                {previewColumns.map((column) => (
                  <th key={column.name} className="whitespace-nowrap px-4 py-2.5 font-medium">
                    {column.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {dataset.preview.map((row, index) => (
                <tr key={index} className="border-b border-background-200/60 last:border-0">
                  {previewColumns.map((column) => (
                    <td key={column.name} className="max-w-48 truncate px-4 py-2.5 text-foreground-700">
                      {row[column.name] || "—"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
