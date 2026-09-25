import { useTranslation } from "react-i18next";
import SelectMenu from "@/components/base/SelectMenu";

interface GraphToolbarProps {
  companyOptions: { value: string; label: string }[];
  companyId: string;
  onCompanyChange: (id: string) => void;
  depth: number;
  onDepthChange: (depth: number) => void;
  focusRisk: boolean;
  onToggleFocusRisk: () => void;
  riskPathCount: number;
}

export default function GraphToolbar({
  companyOptions,
  companyId,
  onCompanyChange,
  depth,
  onDepthChange,
  focusRisk,
  onToggleFocusRisk,
  riskPathCount,
}: GraphToolbarProps) {
  const { t } = useTranslation();
  const depthValues = [1, 2, 3];

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-background-200 bg-background-100 p-3 xl:flex-row xl:items-center">
      <SelectMenu
        label={t("graph.toolbar.subject")}
        icon="ri-building-2-line"
        value={companyId}
        options={companyOptions}
        onChange={onCompanyChange}
        className="w-full xl:w-72"
      />

      <div className="flex items-center gap-2">
        <span className="text-xs text-foreground-500">
          {t("graph.toolbar.depth")}
        </span>
        <div className="flex items-center gap-1 rounded-full border border-background-200 bg-background-50 p-1">
          {depthValues.map((value) => {
            const active = value === depth;
            return (
              <button
                key={value}
                type="button"
                onClick={() => onDepthChange(value)}
                className={`cursor-pointer whitespace-nowrap rounded-full px-3 py-1 text-[11px] transition-colors ${
                  active
                    ? "bg-primary-500 font-medium text-background-50"
                    : "text-foreground-600 hover:text-foreground-900"
                }`}
              >
                {t("graph.toolbar.depthValue", { count: value })}
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 xl:ml-auto">
        <button
          type="button"
          onClick={onToggleFocusRisk}
          className={`flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border px-3 py-2 text-xs transition-colors ${
            focusRisk
              ? "border-accent-500/50 bg-accent-500/12 text-accent-400"
              : "border-background-300 text-foreground-700 hover:border-accent-500/50 hover:text-accent-400"
          }`}
        >
          <i className="ri-route-line text-sm"></i>
          {t("graph.toolbar.focus")}
          {riskPathCount > 0 && (
            <span className="rounded-full bg-accent-500/18 px-1.5 font-mono text-[10px] text-accent-400">
              {riskPathCount}
            </span>
          )}
        </button>
      </div>
    </div>
  );
}