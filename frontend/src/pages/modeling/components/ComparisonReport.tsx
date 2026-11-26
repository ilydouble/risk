import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { useModelingWorkbench } from "@/features/modeling/model/useModelingWorkbench";
import { algorithmName } from "./comparisonAlgorithms";
import { box, button, input } from "./presentation";

type Workbench = ReturnType<typeof useModelingWorkbench>;

function object(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" ? value as Record<string, unknown> : {};
}

function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function format(value: unknown, digits = 3) {
  return typeof value === "number" ? value.toFixed(digits) : "—";
}

const metrics = ["f1", "recall", "falsePositiveRate"] as const;

export function ComparisonReport({ report, work }: { report: Record<string, unknown>; work: Workbench }) {
  const { t } = useTranslation();
  const [selection, setSelection] = useState(0);
  const members = Array.isArray(report.members) ? report.members.map(object) : [];
  const options = Array.isArray(report.votingOptions) ? report.votingOptions.map(object) : [];
  const option = options[selection];
  const voters = strings(option?.members);
  const best = members.find((member) => member.status === "completed");

  return (
    <section className={`${box} space-y-4`}>
      <h2 className="font-semibold">{t("modeling.comparison.report")}</h2>
      <p className="text-sm text-foreground-500">{t("modeling.comparison.protocol")}</p>
      <div className="overflow-x-auto">
        <table className="w-full whitespace-nowrap text-left text-sm">
          <thead>
            <tr className="border-b border-background-200">
              {["algorithm", "status", "time", "validationAp", "threshold", ...metrics].map((key) => (
                <th key={key} scope="col" className="p-2">{t(`modeling.comparison.${key}`)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {members.map((member) => {
              const name = String(member.algorithm);
              const test = object(member.test);
              return (
                <tr key={name} className="border-b border-background-100">
                  <th scope="row" className="p-2 font-medium">{algorithmName(name)}</th>
                  <td className="max-w-72 whitespace-normal p-2">
                    {member.status === "failed" ? t("modeling.status.failed") : t("modeling.status.completed")}
                    {typeof member.error === "string" && <span className="block break-words text-xs text-danger-500">{member.error}</span>}
                  </td>
                  <td className="p-2 font-mono">{format(member.durationSeconds, 1)}</td>
                  <td className="p-2 font-mono">{format(member.validationAp)}</td>
                  <td className="p-2 font-mono">{format(member.threshold)}</td>
                  {metrics.map((key) => <td key={key} className="p-2 font-mono">{format(test[key])}</td>)}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {option ? <>
        <label className="block text-sm">
          {t("modeling.comparison.voters")}
          <select className={`${input} mt-1`} value={selection}
            onChange={(event) => setSelection(Number(event.target.value))}>
            {options.map((item, index) => {
              const names = strings(item.members);
              return <option key={names.join(",")} value={index}>
                {names.map(algorithmName).join(" + ")}{index === 0 ? ` · ${t("modeling.comparison.recommended")}` : ""}
              </option>;
            })}
          </select>
        </label>
        <dl className="grid gap-2 sm:grid-cols-3">
          {metrics.map((key) => <div className="rounded-md bg-background-50 p-3" key={key}>
            <dt className="text-xs text-foreground-500">{t(`modeling.comparison.${key}`)}</dt>
            <dd className="font-mono">{format(object(best?.test)[key])} → {format(object(option.test)[key])}</dd>
          </div>)}
        </dl>
        <p className="text-xs text-foreground-500">{t("modeling.comparison.deltaNote")}</p>
        <button className={button} disabled={work.busy || voters.length !== 3}
          onClick={() => void work.publish(work.run!.name, voters)}>
          {t("modeling.comparison.publish")}
        </button>
      </> : <p role="status" className="text-sm text-foreground-500">{t("modeling.comparison.insufficient")}</p>}
    </section>
  );
}
