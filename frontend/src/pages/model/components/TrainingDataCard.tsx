import { useTranslation } from "react-i18next";
import Card from "@/components/base/Card";
import { modelTrainingData } from "@/mocks/modelCard";
import { useLang } from "@/hooks/useLang";

export default function TrainingDataCard() {
  const { t } = useTranslation();
  const { pick } = useLang();

  const facts: { label: string; value: string; icon: string }[] = [
    {
      label: t("model.training.sampleSize"),
      value: modelTrainingData.sampleSize.toLocaleString("en-US"),
      icon: "ri-database-2-line",
    },
    { label: t("model.training.timeWindow"), value: pick(modelTrainingData.timeWindow, modelTrainingData.timeWindowEn), icon: "ri-calendar-line" },
    { label: t("model.training.countries"), value: t("model.training.countriesUnit", { count: modelTrainingData.countries }), icon: "ri-earth-line" },
    { label: t("model.training.features"), value: t("model.training.featuresUnit", { count: modelTrainingData.featureCount }), icon: "ri-stack-line" },
    { label: t("model.training.positiveRate"), value: pick(modelTrainingData.positiveRate, modelTrainingData.positiveRateEn), icon: "ri-percent-line" },
    { label: t("model.training.split"), value: pick(modelTrainingData.splitRatio, modelTrainingData.splitRatioEn), icon: "ri-split-cells-horizontal" },
  ];

  const sources = pick(
    modelTrainingData.sources.join("\u0000"),
    (modelTrainingData.sourcesEn ?? modelTrainingData.sources).join("\u0000"),
  ).split("\u0000");

  return (
    <Card
      title={t("model.training.title")}
      subtitle={t("model.training.subtitle")}
      icon="ri-database-2-line"
      bodyClassName="p-4"
    >
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {facts.map((fact) => (
              <div
                key={fact.label}
                className="rounded-md border border-background-200 bg-background-50 p-3"
              >
                <div className="flex items-center gap-1.5 text-foreground-500">
                  <span className="flex h-4 w-4 items-center justify-center">
                    <i className={`${fact.icon} text-[13px]`}></i>
                  </span>
                  <span className="text-[11px]">{fact.label}</span>
                </div>
                <p className="mt-1.5 font-mono text-[15px] font-semibold text-foreground-950">
                  {fact.value}
                </p>
              </div>
            ))}
          </div>

          <div className="mt-3 rounded-md border border-background-200 bg-background-50 p-3">
            <p className="text-[11px] text-foreground-500">{t("model.training.labelDefinition")}</p>
            <p className="mt-1 text-[12px] text-foreground-900">
              {pick(modelTrainingData.labelDefinition, modelTrainingData.labelDefinitionEn)}
            </p>
          </div>

          <div className="mt-3">
            <p className="mb-2 text-[11px] font-medium text-foreground-700">
              {t("model.training.sources")}
            </p>
            <div className="flex flex-wrap gap-1.5">
              {sources.map((source) => (
                <span
                  key={source}
                  className="rounded-full bg-secondary-500/12 px-2.5 py-0.5 text-[11px] text-secondary-300"
                >
                  {source}
                </span>
              ))}
            </div>
          </div>

          <p className="mt-3 rounded-md border border-background-200/70 bg-background-50 p-2.5 text-[11px] leading-relaxed text-foreground-500">
            {pick(modelTrainingData.note, modelTrainingData.noteEn)}
          </p>
        </div>

        <div className="min-w-0">
          <p className="mb-2 text-[11px] font-medium text-foreground-700">
            {t("model.training.groupsTitle", {
              groups: modelTrainingData.featureGroups,
              count: modelTrainingData.featureCount,
            })}
          </p>
          <ul className="space-y-2.5">
            {modelTrainingData.groups.map((group) => (
              <li key={group.key}>
                <div className="flex items-center justify-between gap-2 text-[11px]">
                  <span className="truncate text-foreground-700">
                    {pick(group.label, group.labelEn)}
                  </span>
                  <span className="shrink-0 font-mono text-foreground-500">
                    {t("model.training.dimUnit", { count: group.count })} · {group.share}%
                  </span>
                </div>
                <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-background-200">
                  <span
                    className="block h-full rounded-full bg-primary-500/70"
                    style={{ width: `${group.share}%` }}
                  ></span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </Card>
  );
}