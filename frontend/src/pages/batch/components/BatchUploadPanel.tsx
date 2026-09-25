import { useRef, useState, type DragEvent } from "react";
import { useTranslation } from "react-i18next";
import { useLang } from "@/hooks/useLang";
import type { BatchRoster } from "@/types";

interface BatchUploadPanelProps {
  roster: BatchRoster | null;
  disabled?: boolean;
  onFile: (fileName: string, text: string) => void;
  onSample: () => void;
  onReset: () => void;
}

const ACCEPT = ".csv,.txt";

export default function BatchUploadPanel({
  roster,
  disabled = false,
  onFile,
  onSample,
  onReset,
}: BatchUploadPanelProps) {
  const { t } = useTranslation();
  const { pick } = useLang();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");

  const readFile = (file: File) => {
    setError("");
    if (!/\.(csv|txt)$/i.test(file.name)) {
      setError(t("batch.upload.errors.type"));
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const text = typeof reader.result === "string" ? reader.result : "";
      if (!text.trim()) {
        setError(t("batch.upload.errors.empty"));
        return;
      }
      onFile(file.name, text);
    };
    reader.onerror = () => setError(t("batch.upload.errors.read"));
    reader.readAsText(file, "utf-8");
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    if (disabled) return;
    const file = event.dataTransfer.files?.[0];
    if (file) readFile(file);
  };

  return (
    <section className="animate-fade-up rounded-lg border border-background-200 bg-background-100 p-4 md:p-5">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-primary-500/12 text-primary-400">
            <i className="ri-upload-cloud-2-line text-[15px]"></i>
          </span>
          <div>
            <h2 className="text-[15px] font-semibold leading-tight text-foreground-950">
              {t("batch.upload.title")}
            </h2>
            <p className="mt-0.5 text-xs text-foreground-500">
              {t("batch.upload.subtitle")}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onSample}
            disabled={disabled}
            className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border border-background-300 px-3 py-2 text-xs text-foreground-700 transition-colors hover:border-accent-400 hover:text-accent-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <i className="ri-file-list-3-line text-sm"></i>
            {t("batch.upload.loadSample")}
          </button>
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            disabled={disabled}
            className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md bg-primary-500 px-3.5 py-2 text-xs font-medium text-background-50 transition-colors hover:bg-primary-600 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <i className="ri-upload-line text-sm"></i>
            {t("batch.upload.chooseFile")}
          </button>
        </div>
      </header>

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) readFile(file);
          event.target.value = "";
        }}
      />

      <div
        onDragOver={(event) => {
          event.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => !disabled && inputRef.current?.click()}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-md border border-dashed px-6 py-8 text-center transition-colors ${
          dragging
            ? "border-primary-400 bg-primary-500/8"
            : "border-background-300 bg-background-50 hover:border-background-400"
        } ${disabled ? "cursor-not-allowed opacity-60" : ""}`}
      >
        <span className="flex h-11 w-11 items-center justify-center rounded-full bg-background-200 text-foreground-500">
          <i className="ri-drag-drop-line text-xl"></i>
        </span>
        <p className="mt-3 text-[13px] font-medium text-foreground-900">
          {t("batch.upload.dropTitle")}
        </p>
        <p className="mt-1 text-xs text-foreground-500">
          {t("batch.upload.dropHint")}
        </p>
      </div>

      {error && (
        <p className="mt-3 flex items-center gap-1.5 rounded-md border border-accent-500/30 bg-accent-500/10 px-3 py-2 text-[11px] text-accent-400">
          <i className="ri-error-warning-line text-[13px]"></i>
          {error}
        </p>
      )}

      {roster && (
        <div className="animate-fade-in mt-4 rounded-md border border-background-200 bg-background-50 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-3">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-secondary-500/14 text-secondary-400">
                <i className="ri-file-chart-line text-[17px]"></i>
              </span>
              <div className="min-w-0">
                <p className="truncate text-[13px] font-medium text-foreground-950">
                  {pick(roster.fileName, roster.fileNameEn)}
                </p>
                <p className="mt-0.5 text-[11px] text-foreground-500">
                  {roster.source === "sample"
                    ? t("batch.upload.sampleLabel")
                    : t("batch.upload.fileLabel")}{" "}
                  ·{" "}
                  {t("batch.upload.importedAt", { time: roster.importedAt })}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={onReset}
              className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border border-background-300 px-3 py-1.5 text-[11px] text-foreground-600 transition-colors hover:border-background-400 hover:text-foreground-950"
            >
              <i className="ri-delete-bin-6-line text-[13px]"></i>
              {t("batch.upload.remove")}
            </button>
          </div>

          <div className="mt-3 grid grid-cols-2 gap-3 border-t border-background-200/70 pt-3 sm:grid-cols-4">
            <div>
              <p className="text-[10px] text-foreground-500">
                {t("batch.upload.statParsed")}
              </p>
              <p className="mt-0.5 font-mono text-base font-semibold text-foreground-950">
                {roster.rawNames.length}
              </p>
            </div>
            <div>
              <p className="text-[10px] text-foreground-500">
                {t("batch.upload.statValid")}
              </p>
              <p className="mt-0.5 font-mono text-base font-semibold text-primary-400">
                {roster.valid}
              </p>
            </div>
            <div>
              <p className="text-[10px] text-foreground-500">
                {t("batch.upload.statInvalid")}
              </p>
              <p className="mt-0.5 font-mono text-base font-semibold text-accent-400">
                {roster.invalid}
              </p>
            </div>
            <div>
              <p className="text-[10px] text-foreground-500">
                {t("batch.upload.statStatus")}
              </p>
              <p className="mt-0.5 flex items-center gap-1 text-[13px] font-medium text-foreground-900">
                <i className="ri-checkbox-circle-line text-[14px] text-primary-400"></i>
                {t("batch.upload.statDone")}
              </p>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}