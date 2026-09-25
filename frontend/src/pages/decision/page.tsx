import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import PageFrame from "@/features/workbench-layout/ui/PageFrame";
import DecisionHeader from "@/pages/decision/components/DecisionHeader";
import CreditLimitPanel from "@/pages/decision/components/CreditLimitPanel";
import TermsPanel from "@/pages/decision/components/TermsPanel";
import MitigationPanel from "@/pages/decision/components/MitigationPanel";
import RuleTable from "@/pages/decision/components/RuleTable";
import { buildDecision } from "@/pages/decision/lib/decision";
import { buildScoreDetail } from "@/features/demo-scenarios/lib/score";
import { findCompany, resolveProfile } from "@/features/demo-scenarios/lib/profile";
import { useLang } from "@/shared/lib/useLang";

export default function DecisionPage() {
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

  const decision = useMemo(() => {
    if (!company) return null;
    const profile = resolveProfile(company);
    const detail = buildScoreDetail(company, profile, lang);
    return buildDecision(company, profile, detail, lang);
  }, [company, lang]);

  if (!company || !decision) {
    return (
      <PageFrame title={t("decision.title")} subtitle={t("decision.notFound.shellSubtitle")}>
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-background-300 bg-background-100 px-6 py-20 text-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-full bg-background-200 text-foreground-500">
            <i className="ri-shield-check-line text-2xl"></i>
          </span>
          <h3 className="mt-4 text-[15px] font-semibold text-foreground-950">
            {t("decision.notFound.title")}
          </h3>
          <p className="mt-1.5 max-w-md text-sm text-foreground-500">
            {t("decision.notFound.desc", { id })}
          </p>
          <Link
            to="/search"
            className="mt-5 flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md bg-primary-500 px-4 py-2 text-xs font-medium text-background-50 transition-colors hover:bg-primary-600"
          >
            <i className="ri-search-line text-sm"></i>
            {t("decision.notFound.back")}
          </Link>
        </div>
      </PageFrame>
    );
  }

  const handleCopy = async () => {
    const text = [
      isEn
        ? `[${company.nameEn} · Credit Decision ${decision.id}]`
        : `【${company.nameCn} · 授信决策单 ${decision.id}】`,
      isEn
        ? `Decision: ${decision.outcomeLabel}`
        : `决策结论：${decision.outcomeLabel}`,
      `${decision.limitLabel}: ${decision.creditLimit}`,
      isEn
        ? `Tenor: ${decision.terms[0].value} | Settlement: ${decision.terms[1].value} | Deposit: ${decision.terms[2].value}`
        : `付款账期：${decision.terms[0].value}｜结算方式：${decision.terms[1].value}｜保证金：${decision.terms[2].value}`,
      isEn
        ? `Risk level ${t(`risk.${company.riskLevel}`)}, ${decision.hitCount} rules hit, valid until ${decision.validUntil}.`
        : `风险等级${t(`risk.${company.riskLevel}`)}，命中规则 ${decision.hitCount} 项，有效期至 ${decision.validUntil}。`,
      isEn ? `Approver: ${decision.approver}` : `审批人：${decision.approver}`,
    ].join("\n");
    try {
      await navigator.clipboard.writeText(text);
      setToast(t("decision.copyOk"));
    } catch {
      setToast(t("decision.copyFail"));
    }
  };

  return (
    <PageFrame
      title={t("decision.title")}
      subtitle={t("decision.subtitle")}
      companyId={company.id}
      actions={
        <>
          <button
            type="button"
            onClick={handleCopy}
            className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border border-background-300 px-3 py-2 text-xs text-foreground-700 transition-colors hover:border-primary-400 hover:text-primary-400"
          >
            <i className="ri-file-copy-line text-sm"></i>
            {t("decision.copyPoints")}
          </button>
          <button
            type="button"
            onClick={() => window.print()}
            className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md bg-primary-500 px-3.5 py-2 text-xs font-medium text-background-50 transition-colors hover:bg-primary-600"
          >
            <i className="ri-printer-line text-sm"></i>
            {t("decision.exportDoc")}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <DecisionHeader company={company} decision={decision} />

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="animate-fade-up" style={{ animationDelay: "40ms" }}>
            <CreditLimitPanel decision={decision} />
          </div>
          <div className="animate-fade-up" style={{ animationDelay: "80ms" }}>
            <TermsPanel decision={decision} />
          </div>
        </div>

        <div className="animate-fade-up" style={{ animationDelay: "120ms" }}>
          <MitigationPanel decision={decision} />
        </div>

        <div className="animate-fade-up" style={{ animationDelay: "160ms" }}>
          <RuleTable decision={decision} />
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