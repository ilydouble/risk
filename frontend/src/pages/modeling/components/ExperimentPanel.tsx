import { ExperimentProfilePanel } from "./ExperimentProfilePanel";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { box, button, secondary } from "./presentation";
import { useTranslation } from "react-i18next";
import type { useModelingWorkbench } from "@/features/modeling/model/useModelingWorkbench";
type Workbench = ReturnType<typeof useModelingWorkbench>;
function object(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null
    ? (value as Record<string, unknown>)
    : {};
}

export function ExperimentPanel({ work }: { work: Workbench }) {
  const { t } = useTranslation();
  const stage = (value: string) =>
    t(`modeling.status.${value}`, { defaultValue: value });
  const report = object(work.run?.result.report);
  const metrics = object(report.metrics);
  const confusion = Array.isArray(metrics.confusionMatrix)
    ? metrics.confusionMatrix
    : [];
  const points = work.events
    .filter(
      (event) =>
        event.kind === "metric" &&
        event.attempt === work.run?.attempts.at(-1)?.number,
    )
    .map((event) => ({
      epoch: event.data.epoch,
      trainLoss: event.data.trainLoss,
      validationLoss: event.data.validationLoss,
    }));

  return work.run ? (
    <>
      <section className={`${box} space-y-4`}>
        <div className="flex flex-wrap justify-between gap-3">
          <div>
            <h2 className="font-semibold">{work.run.name}</h2>
            <p className="mt-1 text-sm text-primary-500">
              {stage(work.run.status)} · {stage(work.run.stage)}
              {work.run.cancelRequested ? ` · ${t("modeling.cancelling")}` : ""}
            </p>
          </div>
          <div className="flex gap-2">
            {["queued", "running"].includes(work.run.status) ? (
              <button
                className={secondary}
                disabled={work.busy || work.run.cancelRequested}
                onClick={() => void work.cancel()}
              >
                {t("modeling.cancel")}
              </button>
            ) : (
              <button
                className={secondary}
                disabled={work.busy}
                onClick={() => void work.rerun()}
              >
                {t("modeling.rerun")}
              </button>
            )}
          </div>
        </div>
        <p className="font-mono text-xs text-foreground-500">
          {t(`modeling.models.${work.run.runnerId}`, {
            defaultValue: work.run.runnerId,
          })}{" "}
          · smoke-v1 · {work.run.epochs} epochs · CPU
        </p>
        {work.run.error && (
          <pre className="max-h-48 overflow-auto whitespace-pre-wrap text-xs text-danger-500">
            {work.run.error}
          </pre>
        )}
        {points.length > 0 && (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={points}>
                <CartesianGrid strokeDasharray="3 3" stroke="#94a3b833" />
                <XAxis dataKey="epoch" />
                <YAxis />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="trainLoss"
                  name={t("modeling.trainLoss")}
                  stroke="#4b79cf"
                />
                <Line
                  type="monotone"
                  dataKey="validationLoss"
                  name={t("modeling.validationLoss")}
                  stroke="#d49a34"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
        <div className="space-y-1 text-xs text-foreground-500">
          {work.run.attempts.map((attempt) => (
            <p key={attempt.number}>
              {t("modeling.attempt")} {attempt.number} · {stage(attempt.status)}{" "}
              · {new Date(attempt.startedAt).toLocaleString()}
            </p>
          ))}
        </div>
      </section>
      {work.run.profile && (
        <ExperimentProfilePanel profile={work.run.profile} />
      )}
      {report.independentReload === true && (
        <section className={`${box} space-y-4`}>
          <h2 className="font-semibold">{t("modeling.report")}</h2>
          <p className="text-xs text-foreground-500">
            {t("modeling.reportNote")}
          </p>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {Object.entries(metrics)
              .filter(([, value]) => typeof value === "number")
              .map(([key, value]) => (
                <div className="rounded-md bg-background-50 p-3" key={key}>
                  <p className="text-xs text-foreground-500">
                    {t(`modeling.metrics.${key}`, { defaultValue: key })}
                  </p>
                  <strong className="font-mono">
                    {Number.isInteger(value)
                      ? String(value)
                      : Number(value).toFixed(4)}
                  </strong>
                </div>
              ))}
          </div>
          {confusion.length === 2 && (
            <div>
              <h3 className="mb-2 text-xs text-foreground-500">
                {t("modeling.confusion")}
              </h3>
              <table className="text-center text-xs">
                <thead>
                  <tr>
                    <th className="p-2" />
                    <th className="p-2">0</th>
                    <th className="p-2">1</th>
                  </tr>
                </thead>
                <tbody>
                  {confusion.map((row, index) => (
                    <tr key={index}>
                      <th className="p-2">{index}</th>
                      {Array.isArray(row) &&
                        row.map((value, column) => (
                          <td
                            className="border border-background-200 px-5 py-2 font-mono"
                            key={column}
                          >
                            {Number(value)}
                          </td>
                        ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <button
            className={button}
            disabled={work.busy}
            onClick={() => void work.publish(work.run!.name)}
          >
            {t("modeling.publish")}
          </button>
        </section>
      )}
      <section className={box}>
        <h2 className="mb-3 font-semibold">{t("modeling.events")}</h2>
        <div className="max-h-72 overflow-auto rounded-lg bg-background-50 p-3 font-mono text-[11px] leading-relaxed">
          {work.events.map((event) => (
            <div key={event.sequence} className="break-words py-1">
              <span className="text-foreground-400">
                #{event.sequence} · A{event.attempt} ·{" "}
              </span>
              {event.kind} {JSON.stringify(event.data)}
            </div>
          ))}
        </div>
      </section>
    </>
  ) : (
    <p className={box}>{t("modeling.emptyRun")}</p>
  );
}
