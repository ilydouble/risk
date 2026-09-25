import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";

interface ModelTabDef {
  key: string;
  labelKey: string;
  icon: string;
  to: string;
}

const TABS: ModelTabDef[] = [
  {
    key: "model-card",
    labelKey: "tabs.modelCard",
    icon: "ri-file-info-line",
    to: "/model-card",
  },
  {
    key: "model",
    labelKey: "tabs.modelEval",
    icon: "ri-line-chart-line",
    to: "/model",
  },
];

function resolveActiveKey(pathname: string): string {
  return pathname.split("/").filter(Boolean)[0] ?? "";
}

export default function ModelTabs() {
  const { t } = useTranslation();
  const location = useLocation();
  const activeKey = resolveActiveKey(location.pathname);

  return (
    <nav
      aria-label={t("tabs.modelAria")}
      className="mb-5 flex items-center gap-1 overflow-x-auto rounded-lg border border-background-200 bg-background-100 p-1"
    >
      {TABS.map((tab) => {
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
            {t(tab.labelKey)}
          </Link>
        );
      })}
    </nav>
  );
}