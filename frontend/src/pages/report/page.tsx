import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import PageFrame from "@/features/workbench-layout/ui/PageFrame";
import ReportHeader from "@/pages/report/components/ReportHeader";
import ReportBody from "@/pages/report/components/ReportBody";
import ReportSidebar, {
  type SectionStatus,
} from "@/pages/report/components/ReportSidebar";
import { useReportStream } from "@/pages/report/hooks/useReportStream";
import { buildReport, flattenSentences } from "@/pages/report/lib/report";
import { buildScoreDetail } from "@/features/demo-scenarios/lib/score";
import { findCompany, resolveProfile } from "@/features/demo-scenarios/lib/profile";
import { useLang } from "@/shared/lib/useLang";
import type { Evidence } from "@/entities/demo/model/types";

export default function ReportPage() {
  const { t } = useTranslation();
  const { isEn, lang } = useLang();
  const { id } = useParams();
  const company = useMemo(() => findCompany(id), [id]);
  const [toast, setToast] = useState("");

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 2600);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const bundle = useMemo(() => {
    if (!company) return null;
    const profile = resolveProfile(company);
    const detail = buildScoreDetail(company, profile, lang);
    const doc = buildReport(company, profile, detail, lang);
    const flat = flattenSentences(doc);
    const evidenceMap: Record<number, Evidence> = {};
    doc.evidence.forEach((item) => {
      evidenceMap[item.number] = item;
    });
    return { profile, detail, doc, flat, evidenceMap };
  }, [company, lang]);

  const total = bundle?.flat.length ?? 0;
  const stream = useReportStream(total);

  const sectionStatus: SectionStatus[] = useMemo(() => {
    if (!bundle) return [];
    return bundle.doc.sections.map((section) => {
      const start = bundle.flat.findIndex((item) => item.sectionId === section.id);
      const count = bundle.flat.filter(
        (item) => item.sectionId === section.id,
      ).length;
      const revealed = Math.max(0, Math.min(count, stream.revealed - start));
      return {
        id: section.id,
        index: section.index,
        title: section.title,
        icon: section.icon,
        revealed,
        count,
      };
    });
  }, [bundle, stream.revealed]);

  if (!company || !bundle) {
    return (
      <PageFrame title={t("report.title")} subtitle={t("report.notFound.shellSubtitle")}>
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-background-300 bg-background-100 px-6 py-20 text-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-full bg-background-200 text-foreground-500">
            <i className="ri-file-text-line text-2xl"></i>
          </span>
          <h3 className="mt-4 text-[15px] font-semibold text-foreground-950">
            {t("report.notFound.title")}
          </h3>
          <p className="mt-1.5 max-w-md text-sm text-foreground-500">
            {t("report.notFound.desc", { id })}
          </p>
          <Link
            to="/search"
            className="mt-5 flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md bg-primary-500 px-4 py-2 text-xs font-medium text-background-50 transition-colors hover:bg-primary-600"
          >
            <i className="ri-search-line text-sm"></i>
            {t("report.notFound.back")}
          </Link>
        </div>
      </PageFrame>
    );
  }

  const { profile, detail, doc, evidenceMap } = bundle;

  const handleCopy = async () => {
    const text = [
      isEn
        ? `[${company.nameEn} · Credit Assessment Report]`
        : `【${company.nameCn} · 授信评估报告】`,
      isEn
        ? `Score ${detail.finalScore} (${detail.grade}), default probability ${company.defaultProb}%, risk level ${t(`risk.${company.riskLevel}`)}.`
        : `信用分 ${detail.finalScore}（${detail.grade}），违约概率 ${company.defaultProb}%，风险等级${t(`risk.${company.riskLevel}`)}。`,
      isEn
        ? `Reference credit limit ${company.creditLimit}.`
        : `参考授信额度 ${company.creditLimit}。`,
      isEn ? (profile.summaryEn ?? profile.summary) : profile.summary,
    ].join("\n");
    try {
      await navigator.clipboard.writeText(text);
      setToast(t("report.copyOk"));
    } catch {
      setToast(t("report.copyFail"));
    }
  };

  return (
    <PageFrame
      title={t("report.title")}
      subtitle={t("report.subtitle")}
      companyId={company.id}
      actions={
        <>
          <button
            type="button"
            onClick={handleCopy}
            className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border border-background-300 px-3 py-2 text-xs text-foreground-700 transition-colors hover:border-primary-400 hover:text-primary-400"
          >
            <i className="ri-file-copy-line text-sm"></i>
            {t("report.copyConclusion")}
          </button>
          <button
            type="button"
            onClick={() => window.print()}
            className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md bg-primary-500 px-3.5 py-2 text-xs font-medium text-background-50 transition-colors hover:bg-primary-600"
          >
            <i className="ri-printer-line text-sm"></i>
            {t("report.exportPdf")}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <ReportHeader
          company={company}
          doc={doc}
          progress={stream.progress}
          revealed={stream.revealed}
          total={total}
          playing={stream.playing}
          done={stream.done}
          onRestart={stream.restart}
          onToggle={stream.toggle}
          onComplete={stream.complete}
        />

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
          <div className="animate-fade-up" style={{ animationDelay: "40ms" }}>
            <ReportBody
              doc={doc}
              evidenceMap={evidenceMap}
              revealed={stream.revealed}
              playing={stream.playing}
              done={stream.done}
            />
          </div>

          <div className="animate-fade-up" style={{ animationDelay: "80ms" }}>
            <ReportSidebar
              doc={doc}
              sectionStatus={sectionStatus}
              revealed={stream.revealed}
              total={total}
            />
          </div>
        </div>
      </div>

      {toast && (
        <div className="animate-fade-in fixed bottom-6 left-1/2 z-40 -translate-x-1/2 rounded-md border border-background-300 bg-background-100 px-4 py-2.5 text-xs text-foreground-900">
          <span className="flex items-center gap-2">
            <i className="ri-checkbox-circle-line text-base text-primary-400"></i>
            {toast}
          </span>
        </div>
      )}
    </PageFrame>
  );
}