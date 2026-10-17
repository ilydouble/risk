import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import * as AuthApi from "@/features/auth/api/authApi";
import { useAuthUser } from "@/features/auth/model/AuthContext";
import { handleApiError } from "@/shared/api/http";
import LanguageSwitcher from "@/shared/ui/LanguageSwitcher";

export default function TopBar({ onMenuClick }: { onMenuClick: () => void }) {
  const { t } = useTranslation();
  const authUser = useAuthUser();
  const displayName = authUser?.displayName ?? authUser?.username ?? "";
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function logout() {
    setBusy(true); setError("");
    try {
      await AuthApi.requestLogout({});
      setOpen(false);
      navigate("/login", { replace: true });
    } catch (failure) {
      setError(handleApiError(failure));
    } finally { setBusy(false); }
  }

  return <header className="sticky top-0 z-20 flex h-16 items-center justify-end border-b border-background-200 bg-background-50/95 px-4 backdrop-blur md:px-6">
    <Dialog.Root open={open} onOpenChange={value => { if (!busy) { setOpen(value); setError(""); } }}>
      <Dialog.Trigger asChild>
        <button type="button" aria-label={`${displayName} · ${t("topbar.accountMenu")}`} className="flex h-9 items-center gap-2 rounded-md border border-background-200 bg-background-100 pl-1 pr-3 text-left hover:border-primary-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500">
          <span aria-hidden="true" className="flex h-7 w-7 items-center justify-center rounded-md bg-secondary-500/20 text-secondary-300"><i className="ri-user-3-line text-[15px]" /></span>
          <span className="max-w-40 leading-tight"><span className="block truncate text-xs font-medium text-foreground-900">{displayName}</span><span className="block text-[10px] text-foreground-500">{t("topbar.demoEnvironment")}</span></span>
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-transparent" />
        <Dialog.Content aria-describedby={undefined} className="fixed right-4 top-14 z-50 w-64 max-w-[calc(100vw-2rem)] space-y-4 rounded-xl border border-background-200 bg-background-50 p-4 shadow-lg md:right-6">
          <Dialog.Title className="sr-only">{t("topbar.accountMenu")}</Dialog.Title>
          <div className="flex items-center justify-between gap-3"><span className="text-sm text-foreground-600">{t("topbar.language")}</span><LanguageSwitcher /></div>
          {/* Keep navigation accessible on narrow screens without another header control. */}
          <Dialog.Close asChild><button type="button" disabled={busy} onClick={onMenuClick} className="flex w-full items-center gap-2 rounded-lg border border-background-200 px-3 py-2 text-sm text-foreground-700 lg:hidden"><i className="ri-menu-line" aria-hidden="true" />{t("topbar.openNav")}</button></Dialog.Close>
          <button type="button" disabled={busy} onClick={() => void logout()} className="flex w-full items-center justify-center gap-2 rounded-lg border border-background-200 px-3 py-2 text-sm text-foreground-700 hover:bg-background-200 disabled:opacity-50"><i className="ri-logout-box-r-line" aria-hidden="true" />{t("common.logout")}</button>
          {error && <p role="alert" className="text-xs text-danger-600">{error}</p>}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  </header>;
}
