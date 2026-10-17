import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { box, button, secondary } from "./presentation";
import { ModelDeleteButton } from "@/features/modeling/ui/ModelDeleteButton";
import type { useModelingWorkbench } from "@/features/modeling/model/useModelingWorkbench";

type Workbench = ReturnType<typeof useModelingWorkbench>;
export function ModelPanel({ work }: { work: Workbench }) {
  const { t } = useTranslation();
  return <section className={`${box} space-y-5`}>
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><h2 className="font-semibold">{t("modeling.tabs.model")}</h2>
        <p className="mt-2 text-sm text-foreground-500">{t("modeling.versions.note")}</p></div>
      <Link className={button} to="/chat?riskModels=recent">{t("modeling.versions.assistant")}</Link>
    </div>
    {!work.models.length ? <p className="text-sm text-foreground-500">{t("modeling.emptyModel")}</p> :
      <div className="overflow-x-auto"><table className="w-full text-left text-sm">
        <thead><tr>
          {["name", "algorithm", "created", "actions"].map(key => <th key={key} className="p-3">{t(`modeling.versions.${key}`)}</th>)}
        </tr></thead>
        <tbody>{work.models.map(model => <tr key={model.id} className={`border-t border-background-200 ${work.modelId === model.id ? "bg-primary-500/5" : ""}`}>
          <td className="p-3"><p className="font-medium">{model.name}</p><p className="mt-1 font-mono text-xs text-foreground-500">{model.id}</p></td>
          <td className="p-3">{model.algorithm}</td>
          <td className="whitespace-nowrap p-3">{new Date(model.createdAt).toLocaleString()}</td>
          <td className="p-3"><div className="flex items-center gap-3">
            <button className={secondary} onClick={() => work.select("model", model.id)}>{t("modeling.versions.view")}</button>
            <ModelDeleteButton model={model} onDeleted={() => void work.refresh()} />
          </div></td>
        </tr>)}</tbody>
      </table></div>}
    {work.model && <div className="space-y-4 border-t border-background-200 pt-5">
      <h3 className="font-semibold">{work.model.name}</h3>
      <dl className="grid gap-3 text-sm sm:grid-cols-2">
        <div><dt className="text-foreground-500">{t("modeling.versions.run")}</dt><dd><Link className="break-all text-primary-500 underline" to={`/modeling?tab=run&run=${work.model.runId}`}>{work.model.runId}</Link></dd></div>
        <div><dt className="text-foreground-500">{t("modeling.versions.size")}</dt><dd>{(work.model.size / 1024 / 1024).toFixed(2)} MiB</dd></div>
      </dl>
      <p className="text-sm text-foreground-500">{t("modeling.modelNote")}</p>
      <p className="break-all font-mono text-xs">SHA-256 {work.model.sha256}</p>
      <details><summary className="cursor-pointer text-sm">{t("modeling.versions.report")}</summary>
        <pre className="mt-3 max-h-80 overflow-auto rounded-lg bg-background-50 p-3 text-xs">{JSON.stringify(work.model.report, null, 2)}</pre>
      </details>
      <div className="flex flex-wrap gap-3">
        <button className={secondary} disabled={work.busy} onClick={() => void work.download()}>{t("modeling.download")}</button>
        <Link className={button} to={`/chat?riskModel=${encodeURIComponent(work.model.id)}`}>{t("modeling.versions.useAssistant")}</Link>
      </div>
    </div>}
  </section>;
}
