import { useTranslation } from "react-i18next";
import type { ModelingRun } from "@/entities/modeling/model/types";
import { box } from "./presentation";

export function ExperimentConfigurationPanel({ run }: { run: ModelingRun }) {
  const { t } = useTranslation();
  const config = run.configuration;
  return <section className={`${box} space-y-4`}>
    <h2 className="font-semibold">{t("modeling.config.title")}</h2>
    {config ? <>
      <div className="grid gap-3 md:grid-cols-2">
        {(["requestedParameters", "resolvedParameters"] as const).map((key) =>
          <div key={key} className="min-w-0">
            <h3 className="mb-2 text-xs text-foreground-500">{t(`modeling.config.${key}`)}</h3>
            <pre className="overflow-auto rounded-md bg-background-50 p-3 text-xs">
              {JSON.stringify(config[key], null, 2)}
            </pre>
          </div>)}
      </div>
      <p className="break-all font-mono text-[10px] text-foreground-500">
        v{config.configVersion} · SHA-256 {config.schemaDigest}
      </p>
    </> : <p className="text-xs text-foreground-500">{t("modeling.config.legacy")}</p>}
    {run.actualCounts && <div>
      <h3 className="mb-2 text-sm">{t("modeling.config.actual")}</h3>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {(["targets", "train", "validation", "test"] as const).map((key) =>
          <div key={key} className="rounded-md bg-background-50 p-3 text-sm">
            <span className="block text-xs text-foreground-500">{t(`modeling.config.counts.${key}`)}</span>
            <strong>{run.actualCounts?.[key]?.toLocaleString() ?? "—"}</strong>
          </div>)}
      </div>
    </div>}
  </section>;
}
