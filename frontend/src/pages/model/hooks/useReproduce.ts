import { useCallback, useEffect, useRef, useState } from "react";
import {
  buildReproduceRun,
  type Lang,
} from "@/pages/model/lib/eval";
import type { EvalDashboard, ReproduceRun } from "@/entities/demo/model/types";

export interface ReproduceController {
  run: ReproduceRun | null;
  stepIndex: number;
  done: boolean;
  start: (key: string) => void;
  restart: () => void;
  close: () => void;
}

/**
 * Drives the "复现" (reproduce) run: reveals each pipeline step in sequence and
 * flips to the verified result when the run finishes. Runs are deterministic —
 * the same target always yields the same run id, logs and result.
 */
export function useReproduce(
  dashboard: EvalDashboard,
  lang: Lang = "zh",
): ReproduceController {
  const [run, setRun] = useState<ReproduceRun | null>(null);
  const [stepIndex, setStepIndex] = useState(0);
  const [done, setDone] = useState(false);
  const timer = useRef<number | null>(null);

  const clearTimer = useCallback(() => {
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
  }, []);

  const start = useCallback(
    (key: string) => {
      clearTimer();
      setRun(buildReproduceRun(dashboard, key, lang));
      setStepIndex(0);
      setDone(false);
    },
    [dashboard, lang, clearTimer],
  );

  const restart = useCallback(() => {
    if (run) start(run.target);
  }, [run, start]);

  const close = useCallback(() => {
    clearTimer();
    setRun(null);
    setStepIndex(0);
    setDone(false);
  }, [clearTimer]);

  useEffect(() => {
    if (!run || done) return clearTimer;

    if (stepIndex >= run.steps.length) {
      timer.current = window.setTimeout(() => setDone(true), 280);
      return clearTimer;
    }

    const duration = run.steps[stepIndex]?.durationMs ?? 500;
    timer.current = window.setTimeout(
      () => setStepIndex((index) => index + 1),
      duration,
    );
    return clearTimer;
  }, [run, stepIndex, done, clearTimer]);

  useEffect(() => clearTimer, [clearTimer]);

  return { run, stepIndex, done, start, restart, close };
}
