import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  buildBatchRun,
  buildBatchRows,
  buildBatchSummary,
  type Lang,
} from "@/pages/batch/lib/batch";
import type {
  BatchRoster,
  BatchRow,
  BatchRun,
  BatchSummary,
} from "@/entities/demo/model/types";

export interface BatchController {
  run: BatchRun | null;
  rows: BatchRow[];
  summary: BatchSummary;
  started: boolean;
  stepIndex: number;
  done: boolean;
  start: () => void;
  reset: () => void;
}

/**
 * Drives a batch evaluation run: reveals each pipeline step in sequence, then
 * flips to the finished result. Rows and summary are derived deterministically
 * from the roster, so the same list always produces the same scores and order.
 */
export function useBatchRun(
  roster: BatchRoster | null,
  lang: Lang = "zh",
): BatchController {
  const [started, setStarted] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  const [done, setDone] = useState(false);
  const timer = useRef<number | null>(null);

  const run = useMemo(
    () => (roster ? buildBatchRun(roster, lang) : null),
    [roster, lang],
  );
  const rows = useMemo(
    () => (roster ? buildBatchRows(roster.rawNames, lang) : []),
    [roster, lang],
  );
  const summary = useMemo(() => buildBatchSummary(rows, lang), [rows, lang]);

  const clearTimer = useCallback(() => {
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
  }, []);

  const start = useCallback(() => {
    clearTimer();
    setStarted(true);
    setStepIndex(0);
    setDone(false);
  }, [clearTimer]);

  const reset = useCallback(() => {
    clearTimer();
    setStarted(false);
    setStepIndex(0);
    setDone(false);
  }, [clearTimer]);

  // A new roster invalidates any previous run.
  useEffect(() => {
    reset();
  }, [roster, reset]);

  useEffect(() => {
    if (!started || !run || done) return clearTimer;

    if (stepIndex >= run.steps.length) {
      timer.current = window.setTimeout(() => setDone(true), 260);
      return clearTimer;
    }

    const duration = run.steps[stepIndex]?.durationMs ?? 500;
    timer.current = window.setTimeout(
      () => setStepIndex((index) => index + 1),
      duration,
    );
    return clearTimer;
  }, [run, started, stepIndex, done, clearTimer]);

  useEffect(() => clearTimer, [clearTimer]);

  return { run, rows, summary, started, stepIndex, done, start, reset };
}