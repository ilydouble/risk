import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import type { ModelingRun } from "@/entities/modeling/model/types";

export function ExperimentActivity({ run, checkedAt, error, epoch }: {
  run: ModelingRun; checkedAt?: number; error: string; epoch?: number;
}) {
  const { t } = useTranslation();
  const [now, setNow] = useState(Date.now);
  const active = run.status === "queued" || run.status === "running";
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [active]);
  if (!active) return null;
  const delayed = Boolean(error) || (checkedAt !== undefined && now - checkedAt > 15_000);
  const expired = run.heartbeatExpiresAt && Date.parse(run.heartbeatExpiresAt) <= now;
  const heartbeat = delayed ? "queryFailed" : run.status === "queued" ? "queued"
    : run.workerAlive === false || expired ? "stale"
    : run.workerAlive === true ? "alive" : "checking";
  const stage = ["validating", "preparing", "training", "evaluating", "uploading"].includes(run.stage)
    ? run.stage : "starting";
  return <div role="status" aria-live="polite"
    className="space-y-2 rounded-lg border border-primary-400/30 bg-primary-500/5 p-4 text-sm">
    <p className="flex items-center gap-2 font-medium">
      <span aria-hidden="true" className="h-3 w-3 animate-pulse rounded-full bg-primary-500" />
      {t(`modeling.activity.${heartbeat}`)}
    </p>
    <p>{t(`modeling.activity.stages.${stage}`)}</p>
    {epoch !== undefined && <p>{t("modeling.activity.epoch", { current: epoch, total: run.epochs })}</p>}
    <p className="text-xs text-foreground-500">
      {t("modeling.activity.elapsed", {
        minutes: Math.max(0, Math.floor((now - Date.parse(run.createdAt)) / 60_000)),
      })}
      {checkedAt !== undefined && ` · ${t("modeling.activity.checked", {
        seconds: Math.max(0, Math.floor((now - checkedAt) / 1000)),
      })}`}
    </p>
    {error && <p className="text-xs text-danger-500">{error}</p>}
    <p className="text-xs text-foreground-500">{t("modeling.activity.background")}</p>
  </div>;
}
