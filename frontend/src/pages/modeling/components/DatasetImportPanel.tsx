import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { inspectPackage } from "@/features/dataset-delivery/lib/package";
import type { useModelingWorkbench } from "@/features/modeling/model/useModelingWorkbench";
import { box, button, input } from "./presentation";

type Workbench = ReturnType<typeof useModelingWorkbench>;

export function DatasetImportPanel({ work }: { work: Workbench }) {
  const { t } = useTranslation();
  const previewSequence = useRef(0);
  const [previewing, setPreviewing] = useState(false);
  const [file, setFile] = useState<File>();
  const [entries, setEntries] = useState<{ filename: string; size: number }[]>(
    [],
  );
  const [previewError, setPreviewError] = useState("");
  const [name, setName] = useState("");
  const preview = async (chosen?: File) => {
    const sequence = ++previewSequence.current;
    setFile(chosen);
    setEntries([]);
    setPreviewError("");
    if (!chosen) { setPreviewing(false); return; }
    setName(chosen.name.replace(/\.zip$/i, ""));
    setPreviewing(true);
    try {
      const items = await inspectPackage(chosen);
      if (sequence !== previewSequence.current) return;
      setEntries(items);
    } catch (error) {
      if (sequence === previewSequence.current)
        setPreviewError(error instanceof Error ? error.message : t("modeling.errors.file"));
    } finally {
      if (sequence === previewSequence.current) setPreviewing(false);
    }
  };

  return (
    <>
      <section className={`${box} space-y-4`}>
        <h2 className="font-semibold">已有标准训练数据包 · 直接导入</h2>
        <p className="text-sm text-foreground-500">仅用于已完成模型适配的契约 ZIP。请按所选适配器的契约在本地准备训练包后上传。</p>
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
          <div key={item.id} className="space-y-2 text-sm">
            <div className="flex justify-between gap-3">
              <span>{item.name}</span>
              <span className="text-foreground-500">
                {item.trainable
                  ? t("modeling.available")
                  : t(`modeling.capabilityReasons.${item.reason}`)}
              </span>
            </div>
            {item.id === "riskgnn" && item.trainable && (
              <div className="border-t border-background-200 pt-2">
                <h3>{t("modeling.comparison.enable")}</h3>
                <p className="mt-1 text-xs text-foreground-500">
                  {t("modeling.comparison.capabilityNote")}
                </p>
              </div>
            )}
          </div>
        ))}
      </section>
    </>
  );
}
