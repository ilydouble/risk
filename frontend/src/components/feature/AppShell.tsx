import { useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import Sidebar from "@/components/feature/Sidebar";
import TopBar from "@/components/feature/TopBar";
import CompanyTabs from "@/components/feature/CompanyTabs";
import ModelTabs from "@/components/feature/ModelTabs";

interface AppShellProps {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  headerExtra?: ReactNode;
  companyId?: string;
  modelTabs?: boolean;
  children: ReactNode;
}

const COMPANY_SCOPED_KEYS = new Set(["graph", "score", "report", "decision"]);
const MODEL_SCOPED_KEYS = new Set(["model", "model-card"]);

function resolveActiveKey(pathname: string): string {
  if (pathname === "/") return "overview";
  const seg = pathname.split("/").filter(Boolean)[0] ?? "";
  if (COMPANY_SCOPED_KEYS.has(seg)) return "company";
  if (MODEL_SCOPED_KEYS.has(seg)) return "model";
  return seg;
}

export default function AppShell({
  title,
  subtitle,
  actions,
  headerExtra,
  companyId,
  modelTabs,
  children,
}: AppShellProps) {
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-screen bg-background-50 text-foreground-900">
      <Sidebar
        activeKey={resolveActiveKey(location.pathname)}
        isOpen={mobileOpen}
        onClose={() => setMobileOpen(false)}
      />

      <div className="lg:pl-64">
        <TopBar onMenuClick={() => setMobileOpen(true)} />

        <main className="px-4 py-5 md:px-6 md:py-6">
          <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div>
              <h1 className="font-heading text-xl font-semibold text-foreground-950 md:text-2xl">
                {title}
              </h1>
              {subtitle && (
                <p className="mt-1 text-sm text-foreground-500">{subtitle}</p>
              )}
            </div>
            {actions && (
              <div className="flex flex-wrap items-center gap-2">{actions}</div>
            )}
          </div>

          {companyId && <CompanyTabs companyId={companyId} />}

          {modelTabs && <ModelTabs />}

          {headerExtra}

          {children}
        </main>
      </div>
    </div>
  );
}