import { useCallback, useEffect, useState } from "react";

/**
 * Progressively reveals `total` items one at a time to simulate a streaming
 * generation. Returns playback controls so the UI can pause / resume / skip.
 */
export function useReportStream(total: number, speed = 760) {
  const [revealed, setRevealed] = useState(0);
  const [playing, setPlaying] = useState(true);

  useEffect(() => {
    setRevealed(0);
    setPlaying(total > 0);
  }, [total]);

  useEffect(() => {
    if (!playing) return;
    if (revealed >= total) {
      setPlaying(false);
      return;
    }
    const timer = window.setTimeout(() => {
      setRevealed((value) => Math.min(total, value + 1));
    }, speed);
    return () => window.clearTimeout(timer);
  }, [playing, revealed, total, speed]);

  const restart = useCallback(() => {
    setRevealed(0);
    setPlaying(total > 0);
  }, [total]);

  const toggle = useCallback(() => {
    setPlaying((value) => (value ? false : revealed < total));
  }, [revealed, total]);

  const complete = useCallback(() => {
    setRevealed(total);
    setPlaying(false);
  }, [total]);

  const done = revealed >= total;
  const progress = total === 0 ? 100 : Math.round((revealed / total) * 100);

  return { revealed, playing, done, progress, restart, toggle, complete };
}