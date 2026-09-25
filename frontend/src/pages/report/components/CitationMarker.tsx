import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import EvidenceCard from "@/pages/report/components/EvidenceCard";
import type { Evidence } from "@/entities/demo/model/types";

interface CitationMarkerProps {
  numbers: number[];
  evidenceMap: Record<number, Evidence>;
}

interface PopoverPos {
  top: number;
  left: number;
  width: number;
  placement: "top" | "bottom";
}

export default function CitationMarker({
  numbers,
  evidenceMap,
}: CitationMarkerProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [locked, setLocked] = useState(false);
  const [pos, setPos] = useState<PopoverPos | null>(null);
  const markerRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);
  const closeTimer = useRef<number | undefined>(undefined);

  const items = numbers
    .map((number) => evidenceMap[number])
    .filter((item): item is Evidence => Boolean(item));

  const computePos = () => {
    const el = markerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const width = Math.min(344, window.innerWidth - 24);
    const left = Math.min(
      Math.max(12, rect.left + rect.width / 2 - width / 2),
      window.innerWidth - width - 12,
    );
    const placeTop = rect.top > 320 && window.innerHeight - rect.bottom < 320;
    setPos({
      top: placeTop ? rect.top - 10 : rect.bottom + 10,
      left,
      width,
      placement: placeTop ? "top" : "bottom",
    });
  };

  const show = () => {
    if (closeTimer.current) window.clearTimeout(closeTimer.current);
    computePos();
    setOpen(true);
  };

  const scheduleHide = () => {
    if (locked) return;
    closeTimer.current = window.setTimeout(() => setOpen(false), 150);
  };

  useEffect(() => {
    return () => {
      if (closeTimer.current) window.clearTimeout(closeTimer.current);
    };
  }, []);

  useEffect(() => {
    if (!locked) return;
    const onDocMouseDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (
        !markerRef.current?.contains(target) &&
        !popRef.current?.contains(target)
      ) {
        setLocked(false);
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDocMouseDown);
    return () => document.removeEventListener("mousedown", onDocMouseDown);
  }, [locked]);

  if (items.length === 0) return null;

  return (
    <>
      <button
        ref={markerRef}
        type="button"
        aria-label={t("report.citation.aria", { count: items.length })}
        onMouseEnter={show}
        onMouseLeave={scheduleHide}
        onClick={(event) => {
          event.stopPropagation();
          setLocked((value) => !value);
          show();
        }}
        className={`ml-0.5 inline-flex cursor-pointer items-center gap-0.5 rounded border border-secondary-500/40 bg-secondary-500/12 px-1 py-[1px] align-super font-mono text-[9px] font-medium leading-none text-secondary-300 transition-colors hover:border-secondary-400 hover:bg-secondary-500/22 hover:text-secondary-200 ${
          locked ? "border-secondary-400 bg-secondary-500/25 text-secondary-200" : ""
        }`}
      >
        <i className="ri-double-quotes-r text-[9px]"></i>
        {numbers.join(",")}
      </button>

      {open && pos && (
        <div
          ref={popRef}
          onMouseEnter={show}
          onMouseLeave={scheduleHide}
          style={{ top: pos.top, left: pos.left, width: pos.width }}
          className={`animate-fade-in fixed z-[70] max-h-[70vh] overflow-y-auto rounded-lg border-2 border-background-300 bg-background-50 p-2 ${
            pos.placement === "top" ? "-translate-y-full" : ""
          }`}
        >
          <div className="mb-1.5 flex items-center justify-between px-1">
            <span className="text-[10px] font-medium text-foreground-500">
              {t("report.citation.source", { count: items.length })}
            </span>
            {locked && (
              <span className="flex items-center gap-1 text-[10px] text-secondary-300">
                <i className="ri-pushpin-2-line text-[11px]"></i>
                {t("report.citation.pinned")}
              </span>
            )}
          </div>
          <div className="space-y-2">
            {items.map((item) => (
              <EvidenceCard key={item.id} evidence={item} />
            ))}
          </div>
        </div>
      )}
    </>
  );
}