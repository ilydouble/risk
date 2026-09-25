import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import StatusDot from "@/components/base/StatusDot";
import { companies } from "@/mocks/companies";
import { DEFAULT_GRAPH_COMPANY_ID } from "@/constants/nav";
import { useLang } from "@/hooks/useLang";

const SEGMENT_LABELS: Record<string, string> = {
  company: "breadcrumb.company",
  graph: "breadcrumb.graph",
  score: "breadcrumb.score",
  report: "breadcrumb.report",
  decision: "breadcrumb.decision",
};

interface Crumbs {
  companyId: string;
  sectionKey: string;
}

function resolveCrumbs(pathname: string, search: string): Crumbs | null {
  const seg = pathname.split("/").filter(Boolean);
  const sectionKey = seg[0] ?? "";
  if (!(sectionKey in SEGMENT_LABELS)) return null;

  if (sectionKey === "graph") {
    const id = new URLSearchParams(search).get("company") ?? DEFAULT_GRAPH_COMPANY_ID;
    return { companyId: id, sectionKey };
  }

  const id = seg[1];
  if (!id) return null;
  return { companyId: id, sectionKey };
}

export default function CompanyBreadcrumb() {
  const { t } = useTranslation();
  const { pick } = useLang();
  const location = useLocation();
  const crumbs = resolveCrumbs(location.pathname, location.search);

  if (!crumbs) return null;

  const company = companies.find((item) => item.id === crumbs.companyId);
  if (!company) return null;

  const sectionLabel = SEGMENT_LABELS[crumbs.sectionKey];
  const isCompanyHome = crumbs.sectionKey === "company";

  return (
    <nav
      aria-label={t("breadcrumb.aria")}
      className="hidden min-w-0 items-center gap-2 lg:flex"
    >
      <StatusDot level={company.riskLevel} tooltip />
      <Link
        to={`/company/${company.id}`}
        title={`${pick(company.nameCn, company.nameEn)} · ${t("breadcrumb.companyProfileSuffix")}`}
        className={`max-w-[180px] truncate text-xs transition-colors hover:text-primary-400 ${
          isCompanyHome
            ? "font-medium text-foreground-950"
            : "text-foreground-700"
        }`}
      >
        {pick(company.nameCn, company.nameEn)}
      </Link>
      <span className="flex h-4 w-4 shrink-0 items-center justify-center text-foreground-400">
        <i className="ri-arrow-right-s-line text-base"></i>
      </span>
      <span className="whitespace-nowrap text-xs font-medium text-foreground-900">
        {t(sectionLabel)}
      </span>
    </nav>
  );
}