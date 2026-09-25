import { useTranslation } from "react-i18next";
import Card from "@/shared/ui/Card";
import { modelPipeline, modelSpecs } from "@/features/demo-scenarios/model/fixtures/modelCard";
import { useLang } from "@/shared/lib/useLang";

export default function ModelArchitectureCard() {
  const { t } = useTranslation();
  const { pick } = useLang();

  return (
    <Card
      title={t("model.architecture.title")}
      subtitle={t("model.architecture.subtitle")}
      icon="ri-node-tree"
      bodyClassName="p-4"
    >
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {modelSpecs.map((spec) => (
          <div
            key={spec.label}
            className="rounded-md border border-background-200 bg-background-50 p-3"
          >
            <div className="flex items-center gap-1.5 text-foreground-500">
              <span className="flex h-4 w-4 items-center justify-center">
                <i className={`${spec.icon} text-[13px]`}></i>
              </span>
              <span className="text-[11px]">{pick(spec.label, spec.labelEn)}</span>
            </div>
            <p className="mt-1.5 font-mono text-[12px] leading-snug text-foreground-900">
              {pick(spec.value, spec.valueEn)}
            </p>
          </div>
        ))}
      </div>

      <div className="mt-4 border-t border-background-200/70 pt-4">
        <p className="mb-3 text-[11px] font-medium text-foreground-700">
          {t("model.architecture.pipeline")}
        </p>
        <div className="flex flex-wrap items-stretch gap-2">
          {modelPipeline.map((step, index) => (
            <div key={step.key} className="flex items-stretch gap-2">
              <div className="flex w-[168px] flex-col rounded-md border border-background-200 bg-background-50 p-3">
                <span className="flex h-7 w-7 items-center justify-center rounded-md bg-primary-500/12 text-primary-400">
                  <i className={`${step.icon} text-[15px]`}></i>
                </span>
                <p className="mt-2 text-[12px] font-medium text-foreground-900">
                  {pick(step.label, step.labelEn)}
                </p>
                <p className="mt-1 text-[10px] leading-relaxed text-foreground-500">
                  {pick(step.desc, step.descEn)}
                </p>
              </div>
              {index < modelPipeline.length - 1 && (
                <span className="flex items-center text-foreground-400">
                  <i className="ri-arrow-right-line text-base"></i>
                </span>
              )}
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}