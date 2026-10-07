import { useTranslation } from "react-i18next";
import type { ResponseGetDataset } from "@/shared/api/generated/schema";

export function DatasetAnalysisPanel({
  dataset,
}: {
  dataset: ResponseGetDataset["dataset"];
}) {
  const { t } = useTranslation();
  const report = dataset.analysis;
  const number = (value: number | null | undefined) =>
    value == null ? "—" : value.toFixed(4);
  if (!report) return null;
  return (
    <div className="space-y-4 border-t border-background-200 pt-4">
      <h3 className="font-semibold">{t("modeling.analysis.title")}</h3>
      <p className="text-xs text-foreground-500">
        {t(`modeling.analysis.scopes.${report.scope}`)} ·{" "}
        {report.totalRows.toLocaleString()} {t("modeling.analysis.rows")}
      </p>
      {Object.keys(report.driftSampleRows).length > 0 && (
        <p className="text-xs text-foreground-500">
          {t("modeling.analysis.driftSample")}:{" "}
          {Object.entries(report.driftSampleRows)
            .map(([name, count]) => `${name}: ${count.toLocaleString()}`)
            .join(" · ")}
        </p>
      )}
      <div className="grid gap-3 sm:grid-cols-3">
        {report.splits.map((split) => (
          <div
            className="rounded-md bg-background-50 p-3 text-xs"
            key={split.name}
          >
            <strong>
              {t(`modeling.analysis.splits.${split.name}`, {
                defaultValue: split.name,
              })}
            </strong>
            <p className="mt-2 font-mono">
              {split.rows.toLocaleString()} ·{" "}
              {(split.positiveRate * 100).toFixed(2)}%
            </p>
            <p className="text-foreground-500">
              {t("modeling.analysis.splitCounts")}
            </p>
          </div>
        ))}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr>
              {[
                "feature",
                "missing",
                "unique",
                "auc",
                "iv",
                "mutualInformation",
                "validationPsi",
                "testPsi",
              ].map((key) => (
                <th className="whitespace-nowrap p-2" key={key}>
                  {t(`modeling.analysis.${key}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {report.features.map((feature) => (
              <tr className="border-t border-background-200" key={feature.name}>
                <td className="p-2 font-mono">
                  {feature.name}
                  {feature.constant
                    ? ` · ${t("modeling.analysis.constant")}`
                    : ""}
                </td>
                <td className="p-2">
                  {(feature.missingRate * 100).toFixed(2)}%
                </td>
                <td className="p-2">{feature.uniqueCount.toLocaleString()}</td>
                <td className="p-2">{number(feature.univariateAuc)}</td>
                <td className="p-2">{number(feature.iv)}</td>
                <td className="p-2">{number(feature.mutualInformation)}</td>
                <td className="p-2">
                  {number(
                    report.drift.find(
                      (item) =>
                        item.name === feature.name &&
                        item.split === "validation",
                    )?.psi,
                  )}
                </td>
                <td className="p-2">
                  {number(
                    report.drift.find(
                      (item) =>
                        item.name === feature.name && item.split === "test",
                    )?.psi,
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {report.warnings.length > 0 && (
        <div className="rounded-md bg-accent-500/10 p-3 text-xs">
          <strong>{t("modeling.analysis.warnings")}</strong>
          {report.warnings.map((warning, index) => (
            <p key={`${warning.feature}-${index}`} className="mt-1">
              {warning.feature}:{" "}
              {t(`modeling.analysis.warningCodes.${warning.code}`, {
                defaultValue: warning.code,
              })}
            </p>
          ))}
        </div>
      )}
      {report.correlations.length > 0 && (
        <details className="text-xs">
          <summary className="cursor-pointer">
            {t("modeling.analysis.correlations")}
          </summary>
          {report.correlations.slice(0, 10).map((pair) => (
            <p key={`${pair.left}-${pair.right}`} className="mt-1 font-mono">
              {pair.left} ↔ {pair.right}: {pair.correlation.toFixed(3)}
            </p>
          ))}
        </details>
      )}
    </div>
  );
}
