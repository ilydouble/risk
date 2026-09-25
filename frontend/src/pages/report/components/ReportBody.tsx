import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import CitationMarker from "@/pages/report/components/CitationMarker";
import type { Evidence, ReportDoc } from "@/entities/demo/model/types";

interface ReportBodyProps {
  doc: ReportDoc;
  evidenceMap: Record<number, Evidence>;
  revealed: number;
  playing: boolean;
  done: boolean;
}

export default function ReportBody({
  doc,
  evidenceMap,
  revealed,
  playing,
  done,
}: ReportBodyProps) {
  const { t } = useTranslation();
  const { indexMap, sectionMeta } = useMemo(() => {
    const map = new Map<string, number>();
    const metas: { id: string; start: number; count: number }[] = [];
    let cursor = 0;
    doc.sections.forEach((section) => {
      const ids = section.paragraphs.flatMap((paragraph) =>
        paragraph.sentences.map((item) => item.id),
      );
      metas.push({ id: section.id, start: cursor, count: ids.length });
      ids.forEach((sentenceId) => {
        map.set(sentenceId, cursor);
        cursor += 1;
      });
    });
    return { indexMap: map, sectionMeta: metas };
  }, [doc]);

  const sectionMetaById = useMemo(() => {
    const result: Record<string, { start: number; count: number }> = {};
    sectionMeta.forEach((meta) => {
      result[meta.id] = { start: meta.start, count: meta.count };
    });
    return result;
  }, [sectionMeta]);

  return (
    <article className="rounded-lg border border-background-200 bg-background-100">
      <header className="border-b border-background-200/70 px-5 py-4">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-primary-500/12 text-primary-400">
            <i className="ri-file-text-line text-[15px]"></i>
          </span>
          <div>
            <h3 className="font-heading text-[15px] font-semibold leading-tight text-foreground-950">
              {doc.title}
            </h3>
            <p className="mt-0.5 text-[11px] text-foreground-500">
              {doc.subtitle}
            </p>
          </div>
        </div>
      </header>

      <div className="px-5 py-5 md:px-7 md:py-6">
        {revealed === 0 && (
          <div className="flex items-center gap-2.5 rounded-md border border-dashed border-background-300 bg-background-50 px-4 py-6 text-[12px] text-foreground-500">
            <i className="ri-loader-4-line animate-spin text-base text-primary-400"></i>
            {t("report.body.generating")}
          </div>
        )}

        {doc.sections.map((section) => {
          const meta = sectionMetaById[section.id];
          const sectionRevealed = Math.max(
            0,
            Math.min(meta.count, revealed - meta.start),
          );
          if (sectionRevealed === 0) return null;
          const sectionComplete = sectionRevealed >= meta.count;

          return (
            <section
              key={section.id}
              id={`report-section-${section.id}`}
              className="scroll-mt-24 pt-5 first:pt-0"
            >
              <div className="mb-3 flex items-center gap-2.5">
                <span className="flex h-6 w-6 items-center justify-center rounded-md bg-background-200/80 font-mono text-[11px] font-semibold text-foreground-700">
                  {String(section.index).padStart(2, "0")}
                </span>
                <span className="flex h-6 w-6 items-center justify-center rounded-md bg-primary-500/12 text-primary-400">
                  <i className={`${section.icon} text-[13px]`}></i>
                </span>
                <h4 className="font-heading text-[14px] font-semibold text-foreground-950">
                  {section.title}
                </h4>
                {!sectionComplete && playing && (
                  <span className="flex items-center gap-1.5 rounded-full bg-accent-500/12 px-2 py-0.5 text-[10px] text-accent-400">
                    <i className="ri-loader-4-line animate-spin text-[11px]"></i>
                    {t("report.body.generatingBadge")}
                  </span>
                )}
                <span className="ml-auto font-mono text-[10px] text-foreground-500">
                  {sectionRevealed}/{meta.count}
                </span>
              </div>

              <div
                className={`space-y-3.5 ${
                  sectionComplete
                    ? ""
                    : "rounded-md bg-accent-500/[0.04] px-3 py-3"
                }`}
              >
                {section.paragraphs.map((paragraph) => (
                  <p
                    key={paragraph.id}
                    className="text-[13.5px] leading-[1.95] text-foreground-800"
                  >
                    {paragraph.sentences.map((item) => {
                      const index = indexMap.get(item.id) ?? 0;
                      if (index >= revealed) return null;
                      const isLatest =
                        index === revealed - 1 && playing && !done;
                      return (
                        <span key={item.id} className="animate-fade-up inline">
                          <span>{item.text}</span>
                          {item.citations.length > 0 && (
                            <CitationMarker
                              numbers={item.citations}
                              evidenceMap={evidenceMap}
                            />
                          )}
                          {isLatest && (
                            <span className="ml-0.5 inline-block h-[14px] w-[2px] translate-y-[2px] animate-pulse-soft bg-primary-400 align-middle"></span>
                          )}{" "}
                        </span>
                      );
                    })}
                  </p>
                ))}
              </div>
            </section>
          );
        })}

        {done && (
          <footer className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-background-200/70 pt-4">
            <p className="flex items-center gap-1.5 text-[11px] text-foreground-500">
              <i className="ri-checkbox-circle-line text-sm text-primary-400"></i>
              {t("report.body.done", { sent: doc.sentenceCount, ev: doc.evidence.length })}
            </p>
            <p className="font-mono text-[10px] text-foreground-500">
              {t("report.body.modelAt", { version: doc.modelVersion, time: doc.generatedAt })}
            </p>
          </footer>
        )}
      </div>
    </article>
  );
}