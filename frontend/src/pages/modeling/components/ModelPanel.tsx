import { useState } from "react";
import { box, button, secondary, input } from "./presentation";
import { useTranslation } from "react-i18next";
import type { useModelingWorkbench } from "@/features/modeling/model/useModelingWorkbench";
type Workbench = ReturnType<typeof useModelingWorkbench>;
export function ModelPanel({ work }: { work: Workbench }) {
  const { t } = useTranslation();
  const [companyIds, setCompanyIds] = useState("");
  return work.model ? (
    <section className={`${box} space-y-4`}>
      <h2 className="font-semibold">{work.model.name}</h2>
      <p className="text-xs text-foreground-500">
        {t(`modeling.models.${work.model.runnerId}`, {
          defaultValue: work.model.runnerId,
        })}
      </p>
      <p className="text-sm text-foreground-500">{t("modeling.modelNote")}</p>
      <p className="break-all font-mono text-xs">SHA-256 {work.model.sha256}</p>
      <button
        className={button}
        disabled={work.busy}
        onClick={() => void work.download()}
      >
        {t("modeling.download")}
      </button>
      <hr className="border-background-200" />
      <h3 className="font-semibold">{t("modeling.predict")}</h3>
      <p className="text-xs text-foreground-500">{t("modeling.predictNote")}</p>
      <textarea
        rows={3}
        className={input}
        value={companyIds}
        onChange={(event) => setCompanyIds(event.target.value)}
        aria-label={t("modeling.enterpriseIds")}
        placeholder={t("modeling.enterpriseIds")}
      />
      <div className="flex gap-2">
        <button
          className={secondary}
          onClick={() =>
            setCompanyIds(work.model!.companies.slice(0, 3).join("\n"))
          }
        >
          {t("modeling.fillExamples")}
        </button>
        <button
          className={button}
          disabled={work.busy || !companyIds.trim()}
          onClick={() => void work.predict(companyIds.trim().split(/[\s,，]+/))}
        >
          {t("modeling.predict")}
        </button>
      </div>
      {work.predictions.length > 0 && (
        <table className="w-full text-left text-sm">
          <thead>
            <tr>
              <th className="py-2">{t("modeling.enterpriseIds")}</th>
              <th>{t("modeling.probability")}</th>
              <th>{t("modeling.label")}</th>
            </tr>
          </thead>
          <tbody>
            {work.predictions.map((prediction, index) => (
              <tr
                key={`${prediction.companyId}-${index}`}
                className="border-t border-background-200"
              >
                <td className="py-2 font-mono">{prediction.companyId}</td>
                <td>{(prediction.probability * 100).toFixed(3)}%</td>
                <td>{prediction.predictedLabel}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  ) : (
    <p className={box}>{t("modeling.emptyModel")}</p>
  );
}
