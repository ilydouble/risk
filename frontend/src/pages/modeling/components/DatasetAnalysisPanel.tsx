import { useState } from "react";
import { useTranslation } from "react-i18next";
import { analysisOf, type ModelingDataset } from "@/entities/modeling/model/types";
import Card from "@/shared/ui/Card";

interface DatasetAnalysisPanelProps {
  dataset: ModelingDataset;
}

type View = "quality" | "signal" | "drift" | "graph";
const percent = (value: number) => `${(value * 100).toFixed(1)}%`;
const number = (value: number | null) => value == null ? "—" : value.toFixed(4);

export default function DatasetAnalysisPanel({ dataset }: DatasetAnalysisPanelProps) {
  const { t } = useTranslation();
  const [view, setView] = useState<View>("quality");
  const analysis = analysisOf(dataset);
  if (!analysis) return null;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 rounded-lg border border-background-200 bg-background-100 p-2">
        {(["quality", "signal", "drift", "graph"] as const).map((item) => (
          <button
            type="button"
            key={item}
            onClick={() => setView(item)}
            className={`rounded-md px-4 py-2 text-xs font-medium ${view === item ? "bg-primary-500 text-white" : "text-foreground-600 hover:bg-background-50"}`}
          >
            {t(`modeling.analysis.views.${item}`)}
          </button>
        ))}
      </div>

      {view === "quality" && (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {[
              [t("modeling.analysis.rows"), analysis.quality.rowCount.toLocaleString()],
              [t("modeling.analysis.columns"), String(analysis.quality.columnCount)],
              [t("modeling.analysis.duplicates"), String(analysis.quality.duplicateSampleIds)],
              [t("modeling.analysis.leakage"), String(analysis.leakageWarnings.length)],
            ].map(([label, value]) => (
              <div key={label} className="rounded-lg border border-background-200 bg-background-100 p-4">
                <p className="text-xs text-foreground-500">{label}</p>
                <p className="mt-1 font-heading text-2xl font-semibold text-foreground-950">{value}</p>
              </div>
            ))}
          </div>
          <Card title={t("modeling.analysis.fields")} icon="ri-table-line" bodyClassName="overflow-x-auto">
            <table className="w-full min-w-[680px] text-left text-xs">
              <thead className="border-b border-background-200 bg-background-50 text-foreground-500">
                <tr><th className="px-4 py-2.5">{t("modeling.analysis.field")}</th><th>{t("modeling.analysis.group")}</th><th>{t("modeling.analysis.type")}</th><th>{t("modeling.analysis.missing")}</th><th>{t("modeling.analysis.unique")}</th></tr>
              </thead>
              <tbody>
                {analysis.quality.columns.map((column) => (
                  <tr key={column.name} className="border-b border-background-200/60 last:border-0">
                    <td className="px-4 py-3 font-mono text-foreground-900">{column.name}</td>
                    <td className="py-3 text-foreground-600">{column.group}</td>
                    <td className="py-3 text-foreground-600">{column.kind}</td>
                    <td className="py-3 text-foreground-600">{percent(column.missingRate)}</td>
                    <td className="py-3 text-foreground-600">{column.uniqueCount}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
          {analysis.leakageWarnings.length > 0 && (
            <Card title={t("modeling.analysis.leakageHints")} icon="ri-alarm-warning-line" bodyClassName="p-5">
              <div className="space-y-2 text-xs text-warning-700">
                {analysis.leakageWarnings.map((item) => <p key={`${item.feature}-${item.reason}`}><b className="font-mono">{item.feature}</b> · {item.reason}</p>)}
              </div>
            </Card>
          )}
        </>
      )}

      {view === "signal" && (
        <Card title={t("modeling.analysis.signalTitle")} icon="ri-pulse-line" bodyClassName="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-xs">
            <thead className="border-b border-background-200 bg-background-50 text-foreground-500"><tr><th className="px-4 py-2.5">{t("modeling.analysis.field")}</th><th>AUC</th><th>IV</th><th>MI</th><th>{t("modeling.analysis.group")}</th></tr></thead>
            <tbody>{analysis.signals.map((item) => <tr key={item.name} className="border-b border-background-200/60"><td className="px-4 py-3 font-mono text-foreground-900">{item.name}</td><td>{number(item.univariateAuc)}</td><td>{number(item.iv)}</td><td>{number(item.mutualInformation)}</td><td>{item.group}</td></tr>)}</tbody>
          </table>
        </Card>
      )}

      {view === "drift" && (
        <div className="grid gap-4 lg:grid-cols-2">
          {["validation", "test"].map((split) => (
            <Card key={split} title={`${split} PSI`} icon="ri-exchange-2-line" bodyClassName="p-5">
              <div className="space-y-2">{(analysis.drift[split] ?? []).slice(0, 12).map((item) => <div key={item.name} className="flex justify-between text-xs"><span className="font-mono text-foreground-700">{item.name}</span><b className={(item.psi ?? 0) >= 0.25 ? "text-danger-500" : "text-foreground-900"}>{number(item.psi)}</b></div>)}</div>
            </Card>
          ))}
        </div>
      )}

      {view === "graph" && (
        <Card title={t("modeling.analysis.graphTitle")} icon="ri-share-line" bodyClassName="p-5">
          {!analysis.graph.available ? (
            <p className="text-sm text-foreground-500">{t("modeling.analysis.noGraph")}</p>
          ) : (
            <pre className="overflow-x-auto rounded-md bg-background-50 p-4 text-xs leading-relaxed text-foreground-700">{JSON.stringify(analysis.graph, null, 2)}</pre>
          )}
        </Card>
      )}

      <p className="text-xs text-foreground-500">{t("modeling.analysis.noRawPreview")}</p>
    </div>
  );
}
