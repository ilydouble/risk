import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { presetCases } from "@/features/demo-scenarios/model/fixtures/overview";
import { useDemoMode } from "@/features/demo-scenarios/model/DemoModeContext";

export default function DemoBanner() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { demoMode } = useDemoMode();

  if (!demoMode) {
    return null;
  }

  return (
    <div className="animate-fade-up mb-5 overflow-hidden rounded-lg border border-accent-500/35 bg-accent-500/8">
      <div className="flex flex-col gap-3 p-4 lg:flex-row lg:items-center">
        <div className="flex items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-accent-500/18 text-accent-400">
            <i className="ri-flashlight-line text-[17px]"></i>
          </span>
          <div>
            <p className="text-sm font-medium text-foreground-950">
              {t("overview.demo.active")}
            </p>
            <p className="mt-0.5 text-xs text-foreground-500">
              {t("overview.demo.desc")}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 lg:ml-auto">
          {presetCases.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => navigate(`/company/${c.companyId}`)}
              className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border border-accent-500/35 bg-background-100/60 px-3 py-1.5 text-xs text-foreground-800 transition-colors hover:border-accent-500 hover:text-accent-400"
            >
              <i className="ri-arrow-right-s-line text-[13px]"></i>
              {t(`overview.preset.${c.id.replace("-", "")}.title`)}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}