import { useEffect, useState } from "react";
import type { Turn } from "@/entities/assistant/model/types";
import { useLang } from "@/shared/lib/useLang";
import { formatTurnDuration } from "../model/duration";

export function TurnDuration({ turn }: { turn: Turn }) {
  const { pick, isEn } = useLang();
  const running = turn.status === "running";
  const [elapsed, setElapsed] = useState(turn.elapsedMs);
  useEffect(() => {
    if (!running || turn.elapsedMs == null) return;
    // Anchor to a server snapshot, then advance with a monotonic clock. Browser wall-clock
    // differences and incremental Item updates must not restart the timer.
    const base = turn.elapsedMs;
    const started = performance.now();
    setElapsed(base);
    const timer = window.setInterval(() => setElapsed(base + performance.now() - started), 1000);
    return () => window.clearInterval(timer);
  }, [turn.id, turn.elapsedMs, running]);

  if (!running) return <>{turn.durationMs == null
    ? pick("耗时未记录", "Duration unavailable")
    : pick("执行了 ", "Ran for ") + formatTurnDuration(turn.durationMs, isEn)}</>;
  return <>{pick("已执行 ", "Running for ")}{elapsed == null ? "…" : formatTurnDuration(elapsed, isEn)}</>;
}
