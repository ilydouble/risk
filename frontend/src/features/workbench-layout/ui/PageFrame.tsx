import type { ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { motion } from "motion/react";
import CompanyTabs from "./CompanyTabs";
import ModelTabs from "./ModelTabs";
import { useLang } from "@/shared/lib/useLang";

interface Props {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  headerExtra?: ReactNode;
  companyId?: string;
  modelTabs?: boolean;
  children: ReactNode;
}

export default function PageFrame({ title, subtitle, actions, headerExtra, companyId, modelTabs, children }: Props) {
  const location = useLocation();
  const { isEn } = useLang();
  return (
    <motion.div key={location.pathname} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.18 }}>
      <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="flex items-center gap-2"><h1 className="font-heading text-xl font-semibold text-foreground-950 md:text-2xl">{title}</h1><span className="rounded-full border border-accent-500/30 bg-accent-500/10 px-2 py-0.5 text-[10px] text-accent-400">{isEn ? "Demo data · no live model" : "演示数据 · 未运行真实模型"}</span></div>
          {subtitle && <p className="mt-1 text-sm text-foreground-500">{subtitle}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {companyId && <CompanyTabs companyId={companyId} />}
      {modelTabs && <ModelTabs />}
      {headerExtra}
      {children}
    </motion.div>
  );
}
