import { useTranslation } from "react-i18next";
import type { ResponseGetRun } from "@/shared/api/generated/schema";
import { box } from "./presentation";

export function ExperimentProfilePanel({
  profile,
}: {
  profile: NonNullable<ResponseGetRun["run"]["profile"]>;
}) {
  const { t } = useTranslation();
  return (
    <section className={`${box} space-y-3 text-xs`}>
      <h2 className="text-base font-semibold">{t("modeling.profile.title")}</h2>
      <p>
        {t("modeling.modelChoice")}:{" "}
        {profile.algorithm}
      </p>
      <p>
        {t("modeling.profile.target")}:{" "}
        {profile.datasetFormat === "sg-comrisk-v1"
          ? t("modeling.profile.sgTarget")
          : profile.target}
      </p>
      <p>
        {t("modeling.profile.selection")}:{" "}
        {t(`modeling.profile.criteria.${profile.selectionMetric}`, {
          defaultValue: profile.selectionMetric,
        })}{" "}
        · {t("modeling.profile.bestEpoch")} {profile.selectedEpoch}
      </p>
      <p>
        {t("modeling.profile.features")}:{" "}
        <span className="font-mono">{profile.selectedFeatures.join(", ")}</span>
      </p>
      <p>
        {t("modeling.profile.preprocessing")}:{" "}
        {String(profile.preprocessing.fitSplit ?? "train")} · seed{" "}
        {profile.seed}
      </p>
      <div className="flex flex-wrap gap-3 font-mono">
        {Object.entries(profile.splits).map(([split, count]) => (
          <span key={split}>
            {split}: {count.toLocaleString()}
          </span>
        ))}
      </div>
      {profile.algorithm === "RiskGNN+" && (
        <>
          <p className="text-foreground-500">{t("modeling.plus.scopeNote")}</p>
          <div className="flex flex-wrap gap-3 font-mono">
            {(["nodes", "edges", "hyperedges", "incidences", "events"] as const).map((key) => (
              typeof profile.graph[key] === "number" && (
                <span key={key}>{t(`modeling.plus.counts.${key}`)}: {Number(profile.graph[key]).toLocaleString()}</span>
              )
            ))}
          </div>
        </>
      )}
      {(["usedInputs", "retainedOnlyInputs"] as const).map((key) => {
        const values = profile.graph[key];
        return Array.isArray(values) && values.length > 0 ? (
          <p key={key}>
            {t(`modeling.profile.${key === "usedInputs" ? "usedInputs" : "retainedInputs"}`)}:
            {" "}<span className="font-mono">{values.map(String).join(", ")}</span>
          </p>
        ) : null;
      })}
      {typeof profile.graph.edgePolicy === "string" && (
        <p>{t("modeling.profile.edgePolicy")}: <span className="font-mono">{profile.graph.edgePolicy}</span></p>
      )}
      <details>
        <summary className="cursor-pointer">
          {t("modeling.profile.provenance")}
        </summary>
        <dl className="mt-2 space-y-2 font-mono text-[10px]">
          <dt>{t("modeling.profile.datasetHash")}</dt>
          <dd className="break-all">{profile.datasetSha256}</dd>
          <dt>{t("modeling.profile.sourceHash")}</dt>
          <dd className="break-all">{profile.codeVersion}</dd>
          <dt>{t("modeling.profile.dependencies")}</dt>
          <dd>
            {Object.entries(profile.dependencies)
              .map(([name, version]) => `${name} ${version}`)
              .join(" · ")}
          </dd>
        </dl>
      </details>
    </section>
  );
}
