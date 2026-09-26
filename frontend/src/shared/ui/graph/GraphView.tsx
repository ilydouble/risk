import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { createGraphController, type GraphStatus } from "./controller";
import type { GraphViewProps } from "./types";

export function GraphView({
  nodes, edges, centerId, selectedId = null, onSelect,
  height = 620, className = "", ariaLabel,
}: GraphViewProps) {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const controllerRef = useRef<ReturnType<typeof createGraphController> | null>(null);
  const selectRef = useRef(onSelect);
  const [status, setStatus] = useState<GraphStatus>("loading");
  const [attempt, setAttempt] = useState(0);
  selectRef.current = onSelect;

  useEffect(() => {
    const controller = createGraphController(
      containerRef.current!,
      (id) => selectRef.current?.(id),
      setStatus,
    );
    controllerRef.current = controller;
    setStatus("loading");
    return () => {
      controllerRef.current = null;
      controller.dispose();
    };
  }, [attempt]);

  useEffect(() => {
    const validSelection = nodes.some((node) => node.id === selectedId) ? selectedId : null;
    controllerRef.current?.update({ nodes, edges, centerId, selectedId: validSelection });
    if (selectedId !== validSelection) selectRef.current?.(null);
  }, [nodes, edges, centerId, selectedId, attempt]);

  const disabled = status !== "ready" || nodes.length === 0;
  return (
    <div className={`relative w-full overflow-hidden rounded-lg border border-background-200 bg-background-50 ${className}`} style={{ height }}>
      <div ref={containerRef} className="absolute inset-0 touch-none" role="region" aria-label={ariaLabel ?? t("graphView.label")} aria-busy={status === "loading"} />
      {status === "error" ? (
        <div role="alert" className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-background-50 text-sm text-foreground-700">
          <p>{t("graphView.error")}</p>
          <button type="button" onClick={() => setAttempt((value) => value + 1)} className="rounded border border-background-300 px-3 py-1.5">{t("graphView.retry")}</button>
        </div>
      ) : (status === "loading" || nodes.length === 0) && (
        <p role="status" className="pointer-events-none absolute inset-0 flex items-center justify-center text-sm text-foreground-500">
          {t(nodes.length === 0 ? "graphView.empty" : "graphView.loading")}
        </p>
      )}
      <div className="pointer-events-none absolute bottom-3 left-3 max-w-[60%] text-[10px] text-foreground-500">{t("graphView.hint")}</div>
      <div className="absolute bottom-3 right-3 flex gap-1.5">
        <button type="button" disabled={disabled} aria-label={t("graphView.zoomIn")} title={t("graphView.zoomIn")} onClick={() => controllerRef.current?.zoom(1.2)} className="h-8 w-8 rounded border border-background-300 bg-background-100 text-foreground-700 disabled:opacity-40">+</button>
        <button type="button" disabled={disabled} aria-label={t("graphView.zoomOut")} title={t("graphView.zoomOut")} onClick={() => controllerRef.current?.zoom(1 / 1.2)} className="h-8 w-8 rounded border border-background-300 bg-background-100 text-foreground-700 disabled:opacity-40">−</button>
        <button type="button" disabled={disabled} onClick={() => controllerRef.current?.reset()} className="h-8 rounded border border-background-300 bg-background-100 px-2.5 text-xs text-foreground-700 disabled:opacity-40">{t("graphView.reset")}</button>
      </div>
    </div>
  );
}
