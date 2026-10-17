import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useTranslation } from "react-i18next";
import { requestDeleteModel } from "@/entities/modeling/api/modelingApi";
import type { ModelingVersion } from "@/entities/modeling/model/types";
import { handleApiError } from "@/shared/api/http";

export function ModelDeleteButton({ model, onDeleted }: {
  model: ModelingVersion;
  onDeleted: () => void;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function remove() {
    setBusy(true); setError("");
    try {
      await requestDeleteModel({ modelId: model.id, confirm: true });
      setOpen(false); onDeleted();
    } catch (cause) {
      setError(handleApiError(cause, { MODELING_RESOURCE_NOT_FOUND: t("modeling.errors.missing") }));
    } finally { setBusy(false); }
  }
  return <Dialog.Root open={open} onOpenChange={value => { if (!busy) { setOpen(value); setError(""); } }}>
    <Dialog.Trigger asChild><button className="text-sm text-danger-600 underline">{t("modeling.versions.delete")}</button></Dialog.Trigger>
    <Dialog.Portal><Dialog.Overlay className="fixed inset-0 z-50 bg-black/40" />
      <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(480px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 space-y-4 rounded-xl border border-background-300 bg-background-100 p-6 shadow-xl">
        <Dialog.Title className="text-lg font-semibold">{t("modeling.versions.deleteTitle")}</Dialog.Title>
        <p className="break-all text-sm font-medium">{model.name} · {model.id}</p>
        <Dialog.Description className="text-sm leading-6 text-foreground-500">{t("modeling.versions.deleteNote")}</Dialog.Description>
        {error && <p role="alert" className="text-sm text-danger-600">{error}</p>}
        <div className="flex justify-end gap-3">
          <Dialog.Close asChild><button disabled={busy} className="rounded-lg border border-background-300 px-4 py-2 text-sm">{t("modeling.versions.cancel")}</button></Dialog.Close>
          <button disabled={busy} onClick={() => void remove()} className="rounded-lg bg-danger-600 px-4 py-2 text-sm text-white disabled:opacity-40">{t(busy ? "modeling.versions.deleting" : "modeling.versions.confirm")}</button>
        </div>
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>;
}
