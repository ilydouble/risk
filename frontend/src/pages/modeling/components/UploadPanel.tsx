import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import Card from "@/shared/ui/Card";

interface UploadPanelProps {
  busy: "" | "uploading" | "queueing";
  onUpload: (file: File, name: string) => Promise<void>;
}

export default function UploadPanel({ busy, onUpload }: UploadPanelProps) {
  const { t } = useTranslation();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const working = busy !== "";

  const choose = (next: File | null) => {
    setFile(next);
    if (next && !name) setName(next.name.replace(/\.zip$/i, ""));
  };

  return (
    <Card
      title={t("modeling.upload.title")}
      subtitle={t("modeling.upload.subtitle")}
      icon="ri-upload-cloud-2-line"
      bodyClassName="p-5"
    >
      <button
        type="button"
        className="flex w-full cursor-pointer flex-col items-center rounded-lg border border-dashed border-background-300 bg-background-50 px-5 py-8 text-center transition hover:border-primary-400"
        onClick={() => input.current?.click()}
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault();
          choose(event.dataTransfer.files[0] ?? null);
        }}
      >
        <i className="ri-file-chart-line text-3xl text-primary-400" />
        <span className="mt-3 text-sm font-medium text-foreground-900">
          {file?.name ?? t("modeling.upload.drop")}
        </span>
        <span className="mt-1 text-xs text-foreground-500">{t("modeling.upload.limit")}</span>
      </button>
      <input
        ref={input}
        type="file"
        accept=".zip,application/zip,application/x-zip-compressed"
        className="hidden"
        onChange={(event) => choose(event.target.files?.[0] ?? null)}
      />
      <label className="mt-4 block text-xs font-medium text-foreground-700">
        {t("modeling.upload.name")}
        <input
          value={name}
          maxLength={128}
          onChange={(event) => setName(event.target.value)}
          className="mt-1.5 w-full rounded-md border border-background-300 bg-background-50 px-3 py-2 text-sm outline-none focus:border-primary-400"
          placeholder={t("modeling.upload.namePlaceholder")}
        />
      </label>
      <button
        type="button"
        disabled={!file || !name.trim() || working || file.size > 512 * 1024 * 1024}
        onClick={() => file && void onUpload(file, name.trim())}
        className="mt-4 w-full rounded-md bg-primary-500 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-primary-600 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {busy === "uploading"
          ? t("modeling.upload.uploading")
          : busy === "queueing"
            ? t("modeling.upload.queueing")
            : t("modeling.upload.action")}
      </button>
    </Card>
  );
}
