import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import Card from "@/shared/ui/Card";
import StatusPill from "@/entities/risk/ui/StatusPill";
import { modelVersionHistory } from "@/features/demo-scenarios/model/fixtures/modelCard";
import { useLang } from "@/shared/lib/useLang";

export default function VersionHistoryCard() {
  const { t } = useTranslation();
  const { pick } = useLang();

  return (
    <Card
      title={t("model.version.title")}
      subtitle={t("model.version.subtitle")}
      icon="ri-git-branch-line"
      bodyClassName="p-4"
    >
      <ol className="relative space-y-4 pl-6">
        <span
          aria-hidden="true"
          className="absolute left-[7px] top-1.5 h-[calc(100%-12px)] w-px bg-background-300"
        ></span>
        {modelVersionHistory.map((entry) => (
          <li key={entry.version} className="relative">
            <span
              className={`absolute -left-6 top-3.5 flex h-3.5 w-3.5 items-center justify-center rounded-full border-2 ${
                entry.current
                  ? "border-primary-400 bg-primary-500"
                  : "border-background-300 bg-background-100"
              }`}
            ></span>

            <Link
              to={`/model?version=${entry.version}`}
              className="group block cursor-pointer rounded-md px-2.5 py-2 transition-colors duration-200 hover:bg-background-200/60"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`font-mono text-[13px] font-semibold ${
                    entry.current ? "text-primary-400" : "text-foreground-900"
                  }`}
                >
                  {entry.version}
                </span>
                <span className="font-mono text-[11px] text-foreground-500">
                  {entry.date}
                </span>
                {entry.current && (
                  <StatusPill level="low" label={t("model.version.current")} size="sm" />
                )}
                <span className="ml-auto flex items-center gap-3 font-mono text-[11px] text-foreground-500">
                  <span>
                    AUC{" "}
                    <span className="text-foreground-800">
                      {entry.auc.toFixed(3)}
                    </span>
                  </span>
                  <span>
                    KS{" "}
                    <span className="text-foreground-800">
                      {entry.ks.toFixed(3)}
                    </span>
                  </span>
                </span>
              </div>

              <p className="mt-1 text-[12px] font-medium text-foreground-700">
                {pick(entry.headline, entry.headlineEn)}
              </p>

              <ul className="mt-1.5 space-y-1">
                {(pick(entry.changes.join("\u0000"), (entry.changesEn ?? entry.changes).join("\u0000")).split("\u0000")).map((change) => (
                  <li
                    key={change}
                    className="flex items-start gap-1.5 text-[11px] leading-relaxed text-foreground-500"
                  >
                    <i className="ri-subtract-line mt-0.5 shrink-0 text-[12px] text-foreground-400"></i>
                    {change}
                  </li>
                ))}
              </ul>

              <span className="mt-2 flex items-center gap-1.5 text-[11px] text-foreground-500 transition-colors duration-200 group-hover:text-primary-400">
                <i className="ri-line-chart-line text-[12px]"></i>
                {t("model.version.viewInDashboard")}
                <i className="ri-arrow-right-line ml-auto text-[12px] transition-transform duration-200 group-hover:translate-x-0.5"></i>
              </span>
            </Link>
          </li>
        ))}
      </ol>
    </Card>
  );
}