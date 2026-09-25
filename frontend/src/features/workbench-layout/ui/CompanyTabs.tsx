import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";

interface CompanyTabsProps {
  companyId: string;
}

interface TabDef {
  key: string;
  label: string;
  icon: string;
  to: string;
}

function resolveActiveKey(pathname: string): string {
  return pathname.split("/").filter(Boolean)[0] ?? "";
}

export default function CompanyTabs({ companyId }: CompanyTabsProps) {
  const { t } = useTranslation();
  const location = useLocation();
  const activeKey = resolveActiveKey(location.pathname);

  const tabs: TabDef[] = [
    {
      key: "company",
      label: t("tabs.companyOverview"),
      icon: "ri-building-2-line",
      to: `/company/${companyId}`,
    },
    {
      key: "graph",
      label: t("tabs.companyGraph"),
      icon: "ri-node-tree",
      to: `/graph?company=${companyId}`,
    },
    {
      key: "score",
      label: t("tabs.companyScore"),
      icon: "ri-bar-chart-box-line",
      to: `/score/${companyId}`,
    },
    {
      key: "report",
      label: t("tabs.companyReport"),
      icon: "ri-file-text-line",
      to: `/report/${companyId}`,
    },
    {
      key: "decision",
      label: t("tabs.companyDecision"),
      icon: "ri-shield-check-line",
      to: `/decision/${companyId}`,
    },
  ];

  return (
    <nav
      aria-label={t("tabs.companyAria")}
      className="mb-5 flex items-center gap-1 overflow-x-auto rounded-lg border border-background-200 bg-background-100 p-1"
    >
      {tabs.map((tab) => {
        const active = activeKey === tab.key;
        return (
          <Link
            key={tab.key}
            to={tab.to}
            className={`flex flex-1 items-center justify-center gap-1.5 whitespace-nowrap rounded-md px-3.5 py-2 text-xs transition-colors duration-200 ${
              active
                ? "bg-primary-500 font-medium text-background-50"
                : "text-foreground-600 hover:bg-background-200/70 hover:text-foreground-900"
            }`}
          >
            <span className="flex h-4 w-4 items-center justify-center">
              <i className={`${tab.icon} text-[15px]`}></i>
            </span>
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}