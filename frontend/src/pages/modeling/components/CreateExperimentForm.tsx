import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import * as ModelingApi from "@/entities/modeling/api/modelingApi";
import type { useModelingWorkbench } from "@/features/modeling/model/useModelingWorkbench";
import type { ResponseRunConfiguration } from "@/shared/api/generated/schema";
import { handleApiError } from "@/shared/api/http";
import { button, input, secondary } from "./presentation";

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
    }).catch((reason) => {
      if (active) setError(handleApiError(reason));
    });
    return () => { active = false; };
  }, [datasetId, datasetName, copiedParameters, copiedName, reload]);

  const language = i18n.language.startsWith("zh") ? "zh" : "en";
  const ui = configuration?.uiSchema.fields;
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
        </div>
        <button className={button}
          disabled={work.busy || !name.trim() || fields.some((field) => !field.valid)}
          onClick={() => void work.create(datasetId, name.trim(), {
            epochs: Number(values.epochs), dataset: { target_count: Number(values["dataset.target_count"]) },
          }, configuration.schemaDigest)}>
          {t("modeling.train")}
        </button>
      </>}
    </section>
  );
}
