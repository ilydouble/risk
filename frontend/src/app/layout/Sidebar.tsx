import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import brandSeal from "@/shared/assets/brand-seal.jpg";
import { NAV_GROUPS } from "@/app/config/nav";

interface SidebarProps {
  activeKey: string;
  isOpen: boolean;
  onClose: () => void;
}

export default function Sidebar({ activeKey, isOpen, onClose }: SidebarProps) {
  const { t } = useTranslation();
  const { pathname, search } = useLocation();
  const inWorkbench = pathname.startsWith("/modeling/");

  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/60 lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        ></div>
      )}

      <aside
        className={`fixed left-0 top-0 z-40 flex h-full w-64 flex-col border-r border-background-200 bg-background-100 transition-transform duration-300 lg:translate-x-0 ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-16 items-center gap-2.5 border-b border-background-200 px-5">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-md border border-primary-300/60 bg-primary-500">
            <img
              src={brandSeal}
              alt={t("brand.alt")}
              title={t("brand.title")}
              className="h-full w-full object-cover"
            />
          </span>
          <div className="leading-tight">
            <p className="font-heading text-[15px] font-semibold text-foreground-950">
              {t("brand.name")}
            </p>
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-foreground-500">
              {t("brand.tagline")}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="ml-auto flex h-7 w-7 cursor-pointer items-center justify-center rounded-md text-foreground-500 hover:bg-background-200 lg:hidden"
            aria-label={t("sidebar.closeNav")}
          >
            <i className="ri-close-line text-lg"></i>
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-4">
          {NAV_GROUPS.map((group, groupIndex) => (
            <div key={group.key} className={groupIndex > 0 ? "mt-5" : undefined}>
              <p className="px-2 pb-2 font-mono text-[10px] uppercase tracking-[0.2em] text-foreground-500">
                {t(group.labelKey)}
              </p>
              <ul className="space-y-1">
                {group.items.map((item) => {
                  const active = activeKey === item.key;
                  return (
                    <li key={item.key}>
                      <Link
                        to={inWorkbench && group.key === "modeling" ? { pathname: item.path, search } : item.path}
                        aria-current={active ? "page" : undefined}
                        onClick={onClose}
                        className={`flex items-center gap-3 rounded-md px-3 py-2.5 text-sm transition-colors duration-200 ${
                          active
                            ? "bg-primary-500/12 font-medium text-primary-400"
                            : "text-foreground-500 hover:bg-background-200/70 hover:text-foreground-900"
                        }`}
                      >
                        <span className="flex h-5 w-5 items-center justify-center">
                          <i className={`${item.icon} text-[17px]`}></i>
                        </span>
                        <span className="whitespace-nowrap">{t(item.labelKey)}</span>
                        {active && (
                          <span className="ml-auto h-1.5 w-1.5 rounded-full bg-primary-500"></span>
                        )}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

      </aside>
    </>
  );
}