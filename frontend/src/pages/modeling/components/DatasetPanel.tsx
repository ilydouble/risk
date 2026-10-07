import SelectMenu from "@/shared/ui/SelectMenu";
import { DatasetAnalysisPanel } from "./DatasetAnalysisPanel";
import { useRef, useState } from "react";
import { BlobReader, ZipReader } from "@zip.js/zip.js";
import { box, button, input } from "./presentation";
import { useTranslation } from "react-i18next";
import type { useModelingWorkbench } from "@/features/modeling/model/useModelingWorkbench";
type Workbench = ReturnType<typeof useModelingWorkbench>;
export function DatasetPanel({ work }: { work: Workbench }) {
  const { t } = useTranslation();
  const previewSequence = useRef(0);
  const [previewing, setPreviewing] = useState(false);
  const [file, setFile] = useState<File>();
  const [entries, setEntries] = useState<{ filename: string; size: number }[]>(
    [],
  );
  const [previewError, setPreviewError] = useState("");
  const [name, setName] = useState("");
  const [epochs, setEpochs] = useState(2);
  const [selectedModel, setSelectedModel] = useState("riskgnn-node-edge");
  const options = work.capabilities
    .filter(
      (item) =>
        item.trainable && work.dataset?.supportedRunnerIds.includes(item.id),
    )
    .map((item) => ({
      value: item.id,
      label: t(`modeling.models.${item.id}`, { defaultValue: item.name }),
    }));
  const modelId = options.some((item) => item.value === selectedModel)
    ? selectedModel
    : (options[0]?.value ?? "");
  const stage = (value: string) =>
    t(`modeling.status.${value}`, { defaultValue: value });
  const preview = async (chosen?: File) => {
    const sequence = ++previewSequence.current;
    setFile(chosen);
    setEntries([]);
    setPreviewError("");
    if (!chosen) return;
    setName(chosen.name.replace(/\.zip$/i, ""));
    setPreviewing(true);
    const reader = new ZipReader(new BlobReader(chosen));
    try {
      const items = await reader.getEntries();
      if (items.length > 128 || chosen.size > 512 * 1024 * 1024)
        throw new Error("limit");
      if (sequence !== previewSequence.current) return;
      setEntries(
        items
          .filter((item) => !item.directory)
          .map((item) => ({
            filename: item.filename,
            size: item.uncompressedSize,
          })),
      );
    } catch {
      if (sequence === previewSequence.current)
        setPreviewError(t("modeling.errors.file"));
    } finally {
      await reader.close();
      if (sequence === previewSequence.current) setPreviewing(false);
    }
  };

  return (
    <>
      <section className={`${box} space-y-4`}>
        <h2 className="font-semibold">{t("modeling.upload.title")}</h2>
        <label className="block cursor-pointer rounded-lg border border-dashed border-background-300 bg-background-50 p-5 text-center text-sm">
          <span>{t("modeling.upload.pick")}</span>
          <input
            aria-label={t("modeling.upload.pick")}
            type="file"
            accept=".zip"
            className="mt-3 block w-full text-xs"
            disabled={work.busy}
            onChange={(event) => void preview(event.target.files?.[0])}
          />
        </label>
        <input
          className={input}
          aria-label={t("modeling.name")}
          placeholder={t("modeling.name")}
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
        {previewError && (
          <p role="alert" className="text-sm text-danger-500">
            {previewError}
          </p>
        )}
        {entries.length > 0 && (
          <div className="max-h-48 overflow-auto rounded-md bg-background-50 p-3 font-mono text-xs">
            {entries.map((entry) => (
              <div
                key={entry.filename}
                className="flex justify-between gap-3 py-1"
              >
                <span className="truncate">{entry.filename}</span>
                <span>{(entry.size / 1024).toFixed(1)} KiB</span>
              </div>
            ))}
          </div>
        )}
        <p className="text-xs text-foreground-500">
          {t("modeling.upload.note")}
        </p>
        <button
          className={button}
          disabled={
            previewing || !file || !name.trim() || !!previewError || work.busy
          }
          onClick={() => file && void work.upload(file, name)}
        >
          {work.uploading
            ? `${t("modeling.upload.progress")} ${work.uploadPercent}%`
            : t("modeling.upload.action")}
        </button>
      </section>
      <section className={`${box} space-y-2`}>
        <h2 className="font-semibold">{t("modeling.catalog")}</h2>
        {work.capabilities.map((item) => (
          <div key={item.id} className="flex justify-between gap-3 text-xs">
            <span>
              {t(`modeling.models.${item.id}`, { defaultValue: item.name })}
            </span>
            <span className="text-foreground-500">
              {item.trainable
                ? t("modeling.available")
                : t(`modeling.capabilityReasons.${item.reason}`)}
            </span>
          </div>
        ))}
      </section>
      {work.dataset && (
        <section className={`${box} space-y-4`}>
          <div className="flex flex-wrap justify-between gap-2">
            <h2 className="font-semibold">{work.dataset.name}</h2>
            <span className="text-sm text-primary-500">
              {stage(work.dataset.status)} · {stage(work.dataset.stage)}
            </span>
          </div>
          {work.dataset.error && (
            <pre className="overflow-auto whitespace-pre-wrap text-xs text-danger-500">
              {work.dataset.error}
            </pre>
          )}
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {Object.entries(work.dataset.counts).map(([key, value]) => (
              <div key={key} className="rounded-md bg-background-50 p-3">
                <span className="block truncate text-xs text-foreground-500">
                  {key}
                </span>
                <strong className="font-mono">{value.toLocaleString()}</strong>
              </div>
            ))}
          </div>
          {work.dataset.sha256 && (
            <p className="break-all font-mono text-[10px] text-foreground-500">
              SHA-256 {work.dataset.sha256}
            </p>
          )}
          <details>
            <summary className="cursor-pointer text-sm">
              {t("modeling.upload.verifiedFiles")} ({work.dataset.files.length})
            </summary>
            <div className="max-h-48 overflow-auto text-xs">
              {work.dataset.files.map((entry) => (
                <div
                  key={entry.path}
                  className="border-b border-background-200 py-2"
                >
                  <p>{entry.path}</p>
                  <p className="break-all font-mono text-[10px] text-foreground-500">
                    {entry.sha256}
                  </p>
                </div>
              ))}
            </div>
          </details>
          <p className="text-xs text-foreground-500">
            {t("modeling.dataFormat")}: {work.dataset.dataFormat ?? "—"}
          </p>
          <DatasetAnalysisPanel dataset={work.dataset} />
          {!options.length && work.dataset.status === "ready" && (
            <p className="text-sm text-foreground-500">
              {t("modeling.analysisOnly")}
            </p>
          )}
          <div className="flex flex-wrap items-end gap-3">
            {options.length > 0 && (
              <SelectMenu
                label={t("modeling.modelChoice")}
                value={modelId}
                options={options}
                onChange={setSelectedModel}
              />
            )}
            <label className="text-xs">
              {t("modeling.epochs")}
              <input
                className={`${input} mt-1 max-w-24`}
                type="number"
                min={1}
                max={20}
                value={epochs}
                onChange={(event) => setEpochs(Number(event.target.value))}
              />
            </label>
            <button
              className={button}
              disabled={
                work.dataset.status !== "ready" ||
                !modelId ||
                work.busy ||
                !Number.isInteger(epochs) ||
                epochs < 1 ||
                epochs > 20
              }
              onClick={() =>
                void work.create(
                  work.dataset!.id,
                  `${work.dataset!.name} · ${new Date().toLocaleTimeString()}`,
                  epochs,
                  modelId,
                )
              }
            >
              {t("modeling.train")}
            </button>
          </div>
        </section>
      )}
    </>
  );
}
