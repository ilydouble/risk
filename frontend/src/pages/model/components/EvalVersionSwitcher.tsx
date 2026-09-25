import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { modelVersionHistory } from "@/features/demo-scenarios/model/fixtures/modelCard";

interface EvalVersionSwitcherProps {
  activeVersion: string;
}

export default function EvalVersionSwitcher({
  activeVersion,
}: EvalVersionSwitcherProps) {
  const { t } = useTranslation();
  return (
    <section className="animate-fade-up rounded-lg border border-background-200 bg-background-100 p-3">
      <div className="mb-2.5 flex items-center gap-2 px-1">
        <span className="flex h-5 w-5 items-center justify-center text-foreground-500">
          <i className="ri-git-branch-line text-[15px]"></i>
        </span>
        <p className="text-xs text-foreground-600">{t("model.switcher.hint")}</p>
      </div>

      <div className="flex items-stretch gap-2 overflow-x-auto pb-1">
        {modelVersionHistory.map((entry) => {
          const active = entry.version === activeVersion;
          return (
            <Link
              key={entry.version}
              to={`/model?version=${entry.version}`}
              className={`group flex min-w-[150px] flex-1 cursor-pointer flex-col gap-1 whitespace-nowrap rounded-md border px-3 py-2.5 transition-colors duration-200 ${
                active
                  ? "border-primary-400 bg-primary-500/12"
                  : "border-background-200 bg-background-50 hover:border-background-300 hover:bg-background-200/50"
              }`}
            >
              <div className="flex items-center gap-2">
                <span
                  className={`font-mono text-[13px] font-semibold ${
                    active ? "text-primary-400" : "text-foreground-900"
                  }`}
                >
                  {entry.version}
                </span>
                {entry.current && (
                  <span className="rounded-full bg-secondary-100 px-1.5 py-0.5 text-[10px] text-secondary-900">
                    {t("model.switcher.current")}
                  </span>
                )}
              </div>
              <span className="font-mono text-[10px] text-foreground-500">
                AUC {entry.auc.toFixed(3)} · KS {entry.ks.toFixed(3)}
              </span>
              <span className="text-[10px] text-foreground-500">{entry.date}</span>
            </Link>
          );
        })}
      </div>
    </section>
  );
}