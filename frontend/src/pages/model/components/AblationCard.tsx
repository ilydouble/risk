import { useTranslation } from "react-i18next";
import Card from "@/components/base/Card";
import type { AblationStudy } from "@/types";

interface AblationCardProps {
  study: AblationStudy;
  onReproduce: () => void;
}

export default function AblationCard({ study, onReproduce }: AblationCardProps) {
  const { t } = useTranslation();
  const top = study.rows[0];

  return (
    <Card
      className="animate-fade-up"
      title={t("model.ablation.title")}
      subtitle={t("model.ablation.subtitle")}
      icon="ri-node-tree"
      bodyClassName="p-4"
      action={
        <button
          type="button"
          onClick={onReproduce}
          className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border border-background-300 px-2.5 py-1.5 text-[11px] text-foreground-600 transition-colors hover:border-primary-400 hover:text-primary-400"
        >
          <i className="ri-refresh-line text-[13px]"></i>
          {t("model.ablation.reproduce")}
        </button>
      }
    >
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_300px]">
        <ol className="space-y-3">
          {study.rows.map((row, index) => {
            const accent = index === 0;
            return (
              <li
                key={row.id}
                className="rounded-md border border-background-200 bg-background-50 p-3"
              >
                <div className="flex items-center gap-2.5">
                  <span
                    className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-md font-mono text-[11px] ${
                      accent
                        ? "bg-accent-500/14 text-accent-400"
                        : "bg-background-200 text-foreground-600"
                    }`}
                  >
                    {index + 1}
                  </span>
                  <span className="text-[13px] font-medium text-foreground-900">
                    {row.label}
                  </span>
                  <span className="rounded-full bg-secondary-500/12 px-2 py-0.5 text-[10px] text-secondary-300">
                    {t("model.ablation.featuresUnit", { count: row.featureCount })}
                  </span>
                  <span className="ml-auto font-mono text-[12px] text-foreground-700">
                    AUC{" "}
                    <span
                      className={accent ? "text-accent-400" : "text-primary-400"}
                    >
                      −{row.aucDrop.toFixed(3)}
                    </span>
                  </span>
                </div>

                <div className="mt-2.5 h-2 w-full overflow-hidden rounded-full bg-background-200">
                  <div
                    className={`h-full rounded-full ${
                      accent ? "bg-accent-500" : "bg-primary-500"
                    }`}
                    style={{ width: `${Math.max(row.importance, 4)}%` }}
                  ></div>
                </div>

                <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-foreground-500">
                  <span>
                    {t("model.ablation.relative")}{" "}
                    <span className="font-mono text-foreground-700">{row.importance}%</span>
                  </span>
                  <span>
                    {t("model.ablation.afterAuc")}{" "}
                    <span className="font-mono text-foreground-700">
                      {row.auc.toFixed(3)}
                    </span>
                  </span>
                  <span>
                    {t("model.ablation.ksChange")}{" "}
                    <span className="font-mono text-foreground-700">
                      −{row.ksDrop.toFixed(3)}
                    </span>
                  </span>
                </div>

                <p className="mt-1.5 text-[11px] leading-relaxed text-foreground-500">
                  {row.note}
                </p>
              </li>
            );
          })}
        </ol>

        <div className="flex flex-col gap-3">
          <div className="rounded-md border border-background-200 bg-background-50 p-4">
            <p className="text-[11px] text-foreground-500">{t("model.ablation.baseline")}</p>
            <div className="mt-2 grid grid-cols-2 gap-3">
              <div>
                <p className="text-[10px] text-foreground-500">AUC</p>
                <p className="mt-0.5 font-mono text-xl font-semibold text-foreground-950">
                  {study.baselineAuc.toFixed(3)}
                </p>
              </div>
              <div>
                <p className="text-[10px] text-foreground-500">KS</p>
                <p className="mt-0.5 font-mono text-xl font-semibold text-foreground-950">
                  {study.baselineKs.toFixed(3)}
                </p>
              </div>
            </div>
          </div>

          {top && (
            <div className="rounded-md border border-accent-500/30 bg-accent-500/8 p-4">
              <p className="flex items-center gap-1.5 text-[11px] text-foreground-500">
                <i className="ri-fire-line text-[13px] text-accent-400"></i>
                {t("model.ablation.topTitle")}
              </p>
              <p className="mt-1.5 text-[14px] font-semibold text-foreground-950">
                {top.label}
              </p>
              <p className="mt-1 text-[11px] leading-relaxed text-foreground-600">
                {t("model.ablation.topDesc", {
                  count: top.featureCount,
                  drop: top.aucDrop.toFixed(3),
                })}
              </p>
            </div>
          )}

          <div className="rounded-md border border-background-200 bg-background-50 p-4">
            <p className="flex items-center gap-1.5 text-[11px] font-medium text-foreground-700">
              <i className="ri-information-line text-[13px] text-foreground-500"></i>
              {t("model.ablation.notesTitle")}
            </p>
            <ul className="mt-2 space-y-2">
              {[
                t("model.ablation.note1"),
                t("model.ablation.note2"),
                t("model.ablation.note3"),
              ].map((text) => (
                <li
                  key={text}
                  className="flex items-start gap-2 text-[11px] leading-relaxed text-foreground-500"
                >
                  <i className="ri-checkbox-blank-circle-line mt-1 text-[7px] text-primary-400"></i>
                  <span>{text}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </Card>
  );
}