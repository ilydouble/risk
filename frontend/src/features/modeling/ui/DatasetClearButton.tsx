import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useTranslation } from "react-i18next";
import { requestClearDataset } from "@/entities/modeling/api/modelingApi";
import type { ModelingDataset } from "@/entities/modeling/model/types";
import { handleApiError } from "@/shared/api/http";

export function DatasetClearButton({ dataset, disabled, onCleared }: {
  dataset: ModelingDataset;
  disabled: boolean;
  onCleared: () => void;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function clear() {
    setBusy(true); setError("");
    try {
      await requestClearDataset({ datasetId: dataset.id, name, confirm: true });
      setOpen(false); onCleared();
    } catch (cause) {
      setError(handleApiError(cause, {
        MODELING_RESOURCE_NOT_FOUND: t("modeling.errors.missing"),
        MODELING_DATASET_BUSY: t("modeling.clear.busy"),
        MODELING_CONFIRMATION_MISMATCH: t("modeling.clear.mismatch"),
      }));
    } finally { setBusy(false); }
  }
  return <Dialog.Root open={open} onOpenChange={value => {
    if (!busy) { setOpen(value); setName(""); setError(""); }
  }}>
    <Dialog.Trigger asChild><button disabled={disabled} className="text-sm text-danger-600 underline disabled:opacity-40">{t("modeling.clear.action")}</button></Dialog.Trigger>
    <Dialog.Portal><Dialog.Overlay className="fixed inset-0 z-50 bg-black/40" />
      <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(520px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 space-y-4 rounded-xl border border-background-300 bg-background-100 p-6 shadow-xl">
        <Dialog.Title className="text-lg font-semibold">{t("modeling.clear.title")}</Dialog.Title>
        <p className="break-all text-sm font-medium">{dataset.name} · {dataset.id}</p>
        <Dialog.Description className="text-sm leading-6 text-foreground-500">{t("modeling.clear.note")}</Dialog.Description>
        <label className="block space-y-2 text-sm">
          <span>{t("modeling.clear.typeName")}</span>
          <input className="w-full rounded-lg border border-background-300 bg-background-50 p-2" value={name} disabled={busy} autoComplete="off" onChange={event => setName(event.target.value)} />
        </label>
        {error && <p role="alert" className="text-sm text-danger-600">{error}</p>}
        <div className="flex justify-end gap-3">
          <Dialog.Close asChild><button disabled={busy} className="rounded-lg border border-background-300 px-4 py-2 text-sm">{t("modeling.versions.cancel")}</button></Dialog.Close>
          <button disabled={busy || disabled || name !== dataset.name} onClick={() => void clear()} className="rounded-lg bg-danger-600 px-4 py-2 text-sm text-white disabled:opacity-40">{t(busy ? "modeling.clear.clearing" : "modeling.clear.confirm")}</button>
        </div>
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>;
}
