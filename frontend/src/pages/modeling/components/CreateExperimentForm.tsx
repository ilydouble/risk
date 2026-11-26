import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import * as ModelingApi from "@/entities/modeling/api/modelingApi";
import type { useModelingWorkbench } from "@/features/modeling/model/useModelingWorkbench";
import type { ResponseRunConfiguration } from "@/shared/api/generated/schema";
import { handleApiError } from "@/shared/api/http";
import { button, input, secondary } from "./presentation";
import { algorithmName } from "./comparisonAlgorithms";

const paths = ["dataset.target_count", "epochs"] as const;

function object(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" ? value as Record<string, unknown> : {};
}

function valueAt(value: unknown, path: string): unknown {
  return path.split(".").reduce<unknown>((current, key) => object(current)[key], value);
}

export function CreateExperimentForm({ work }: { work: ReturnType<typeof useModelingWorkbench> }) {
  const { t, i18n } = useTranslation();
  const [configuration, setConfiguration] = useState<ResponseRunConfiguration["configuration"]>();
  const [values, setValues] = useState<Record<string, string>>({});
  const [name, setName] = useState("");
  const [fusion, setFusion] = useState("");
  const [comparison, setComparison] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const datasetId = work.dataset!.id;
  const datasetName = work.dataset!.name;
  const copied = work.copiedRun?.datasetId === datasetId ? work.copiedRun : null;
  const copiedParameters = copied?.configuration?.resolvedParameters;
  const copiedName = copied?.name;

  useEffect(() => {
    let active = true;
    setConfiguration(undefined);
    setError("");
    void ModelingApi.requestRunConfiguration({ datasetId }).then((response) => {
      if (!active) return;
      const definition = response.configuration;
      setConfiguration(definition);
      setValues(Object.fromEntries(paths.map((path) => [
        path, String(valueAt(copiedParameters ?? definition.defaultParameters, path) ?? ""),
      ])));
      setName(copiedName ?? datasetName);
      const saved = valueAt(copiedParameters, "comparison");
      setComparison(Array.isArray(saved) ? saved.filter((item): item is string => typeof item === "string") : []);
      setFusion(String(copiedParameters
        ? (valueAt(copiedParameters, "fusion") ?? "legacy")
        : (valueAt(definition.defaultParameters, "fusion") ?? "")));
    }).catch((reason) => {
      if (active) setError(handleApiError(reason));
    });
    return () => { active = false; };
  }, [datasetId, datasetName, copiedParameters, copiedName, reload]);

  const language = i18n.language.startsWith("zh") ? "zh" : "en";
  const ui = configuration?.uiSchema.fields;
  const properties = object(configuration?.parameterSchema.properties);
  const fusionRule = object(properties.fusion);
  const available = object(object(properties.comparison).items).enum;
  const algorithms = Array.isArray(available)
    ? available.filter((item): item is string => typeof item === "string") : [];
  const fusionOptions = Array.isArray(fusionRule.enum)
    ? fusionRule.enum.filter((value): value is string => typeof value === "string") : [];
  const fields = paths.map((path) => {
    const schema = path.split(".").reduce<unknown>((current, key) =>
      object(object(current).properties)[key], configuration?.parameterSchema);
    const rule = object(schema);
    const presentation = Array.isArray(ui) ? object(ui.find((item) => object(item).path === path)) : {};
    const label = object(presentation.label)[language];
    const description = object(presentation.description)[language];
    const minimum = typeof rule.minimum === "number" ? rule.minimum : undefined;
    const maximum = typeof rule.maximum === "number" ? rule.maximum : undefined;
    const number = Number(values[path]);
    return {
      path, minimum, maximum,
      label: typeof label === "string" ? label : path,
      description: typeof description === "string" ? description : "",
      valid: rule.type === "integer" && values[path]?.trim() !== "" &&
        Number.isInteger(number) && (minimum === undefined || number >= minimum) &&
        (maximum === undefined || number <= maximum),
    };
  });

  return (
    <section className="space-y-3 border-t border-background-200 pt-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="font-semibold">{t("modeling.train")}</h3>
        <button className={secondary} disabled={work.busy} onClick={() => setReload((n) => n + 1)}>
          {t("modeling.config.reload")}
        </button>
      </div>
      {copied && <p className="text-xs text-primary-500">{t("modeling.config.copied")}</p>}
      {error && <p role="alert" className="text-sm text-danger-500">{error}</p>}
      {work.submitting && <p role="status" className="text-sm text-primary-500">
        {t("modeling.activity.submitting")} {t("modeling.activity.submissionNote")}
      </p>}
      {!configuration && !error && <p role="status">{t("modeling.loading")}</p>}
      {configuration && <>
        <label className="block text-sm">
          {t("modeling.config.name")}
          <input className={`${input} mt-1`} value={name} maxLength={128}
            onChange={(event) => setName(event.target.value)} />
        </label>
        <div className="grid gap-4 md:grid-cols-2">
          {fields.map((field) => <label key={field.path} className="block text-sm">
            {field.label}
            <input type="number" step={1} min={field.minimum} max={field.maximum}
              className={`${input} mt-1`} value={values[field.path] ?? ""}
              aria-invalid={!field.valid}
              onChange={(event) => setValues({ ...values, [field.path]: event.target.value })} />
            <span className="mt-1 block text-xs text-foreground-500">{field.description}</span>
            {!field.valid && <span className="text-xs text-danger-500">
              {t("modeling.config.range", { min: field.minimum, max: field.maximum })}
            </span>}
          </label>)}
          {fusionOptions.length > 0 && <label className="block text-sm">
            {t("modeling.config.fusionLabel")}
            <select className={`${input} mt-1`} value={fusion}
              onChange={(event) => setFusion(event.target.value)}>
              {fusionOptions.map((option) => <option key={option} value={option}>
                {t(`modeling.config.fusionOptions.${option}`, { defaultValue: option })}
              </option>)}
            </select>
            <span className="mt-1 block text-xs text-foreground-500">
              {t("modeling.config.fusionNote")}
            </span>
          </label>}
        </div>
        {algorithms.length > 0 && <fieldset className="space-y-2 text-sm">
          <legend className="font-medium">{t("modeling.comparison.algorithms")}</legend>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={comparison.length > 0}
              onChange={(event) => setComparison(event.target.checked ? algorithms : [])} />
            {t("modeling.comparison.enable")}
          </label>
          {comparison.length > 0 && <>
            <div className="flex flex-wrap gap-4">
              {algorithms.map((algorithm) => <label key={algorithm} className="flex items-center gap-2">
                <input type="checkbox" checked={comparison.includes(algorithm)}
                  disabled={comparison.length === 1 && comparison.includes(algorithm)}
                  onChange={(event) => setComparison(comparison.filter((item) => item !== algorithm)
                    .concat(event.target.checked ? [algorithm] : []))} />
                {algorithmName(algorithm)}
              </label>)}
            </div>
            <p className="text-xs text-foreground-500">{t("modeling.comparison.requirement")}</p>
          </>}
        </fieldset>}
        <button className={button}
          disabled={work.busy || (comparison.length > 0 && comparison.length < 3) || !name.trim() || fields.some((field) => !field.valid) ||
            (fusionOptions.length > 0 && !fusionOptions.includes(fusion))}
          onClick={() => void work.create(datasetId, name.trim(), {
            epochs: Number(values.epochs), dataset: { target_count: Number(values["dataset.target_count"]) },
            ...(fusionOptions.length > 0 ? { fusion } : {}),
            ...(algorithms.length > 0 && comparison.length > 0 ? { comparison } : {}),
          }, configuration.schemaDigest)}>
          {t(work.submitting ? "modeling.activity.submitting" : "modeling.train")}
        </button>
      </>}
    </section>
  );
}
