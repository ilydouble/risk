import { useTranslation } from "react-i18next";
import {
  LANGUAGE_STORAGE_KEY,
  type AppLanguage,
} from "@/i18n";

const OPTIONS: { code: AppLanguage; label: string }[] = [
  { code: "zh", label: "中" },
  { code: "en", label: "EN" },
];

export default function LanguageSwitcher() {
  const { i18n } = useTranslation();
  const current: AppLanguage = (i18n.resolvedLanguage ?? "zh").startsWith("en")
    ? "en"
    : "zh";

  const change = (code: AppLanguage) => {
    i18n.changeLanguage(code);
    try {
      window.localStorage.setItem(LANGUAGE_STORAGE_KEY, code);
    } catch {
      /* ignore */
    }
  };

  return (
    <div
      role="group"
      aria-label="Language"
      className="flex items-center gap-1 rounded-full border border-background-200 bg-background-100 p-1"
    >
      {OPTIONS.map((option) => {
        const active = current === option.code;
        return (
          <button
            key={option.code}
            type="button"
            onClick={() => change(option.code)}
            aria-pressed={active}
            className={`flex h-6 min-w-[28px] cursor-pointer items-center justify-center rounded-full px-2 text-[11px] font-medium transition-colors ${
              active
                ? "bg-primary-500 text-background-50"
                : "text-foreground-500 hover:text-foreground-900"
            }`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}