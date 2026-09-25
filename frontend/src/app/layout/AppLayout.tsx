import { useEffect, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";

const COMPANY_SCOPED_KEYS = new Set(["graph", "score", "report", "decision"]);
const MODEL_SCOPED_KEYS = new Set(["model", "model-card"]);

function activeKey(pathname: string): string {
  if (pathname === "/") return "overview";
  const segment = pathname.split("/").filter(Boolean)[0] ?? "";
  if (COMPANY_SCOPED_KEYS.has(segment)) return "company";
  if (MODEL_SCOPED_KEYS.has(segment)) return "model";
  return segment;
}

export default function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [toast, setToast] = useState("");

  useEffect(() => {
    const show = (event: Event) => setToast((event as CustomEvent<string>).detail);
    const expire = () => navigate("/login", { replace: true });
    window.addEventListener("risk:api-error", show);
    window.addEventListener("risk:session-expired", expire);
    return () => {
      window.removeEventListener("risk:api-error", show);
      window.removeEventListener("risk:session-expired", expire);
    };
  }, [navigate]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 3500);
    return () => window.clearTimeout(timer);
  }, [toast]);

  return (
    <div className="min-h-screen bg-background-50 text-foreground-900">
      <Sidebar activeKey={activeKey(location.pathname)} isOpen={mobileOpen} onClose={() => setMobileOpen(false)} />
      <div className="lg:pl-64">
        <TopBar onMenuClick={() => setMobileOpen(true)} />
        <main className="px-4 py-5 md:px-6 md:py-6"><Outlet /></main>
      </div>
      {toast && <div role="alert" className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-md border border-background-300 bg-background-100 px-4 py-2.5 text-xs text-foreground-900">{toast}</div>}
    </div>
  );
}
