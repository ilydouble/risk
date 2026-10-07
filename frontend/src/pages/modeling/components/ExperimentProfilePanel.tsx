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
        {t(`modeling.models.${profile.runnerId}`, {
          defaultValue: profile.runnerId,
        })}
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
