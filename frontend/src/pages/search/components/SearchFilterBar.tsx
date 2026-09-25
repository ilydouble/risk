import SelectMenu from "@/shared/ui/SelectMenu";
import StatusDot from "@/entities/risk/ui/StatusDot";
import { useTranslation } from "react-i18next";
import { useLang } from "@/shared/lib/useLang";
import {
  regionOptions,
  riskOptions,
  sectorOptions,
  sortOptions,
  type SortKey,
} from "@/pages/search/lib/query";
import type { Company, RiskLevel } from "@/entities/demo/model/types";

interface SearchFilterBarProps {
  region: string;
  onRegionChange: (value: string) => void;
  sector: string;
  onSectorChange: (value: string) => void;
  risks: RiskLevel[];
  onToggleRisk: (risk: RiskLevel) => void;
  sort: SortKey;
  onSortChange: (value: SortKey) => void;
  activeCount: number;
  onReset: () => void;
  companies: Company[];
}

export default function SearchFilterBar({
  region,
  onRegionChange,
  sector,
  onSectorChange,
  risks,
  onToggleRisk,
  sort,
  onSortChange,
  activeCount,
  onReset,
  companies,
}: SearchFilterBarProps) {
  const { t } = useTranslation();
  const { pick } = useLang();
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-background-200 bg-background-100 p-3 xl:flex-row xl:items-center">
      <div className="flex flex-wrap items-center gap-2">
        <SelectMenu
          label={t("search.filterRegion")}
          icon="ri-earth-line"
          value={region}
          options={regionOptions(companies).map((o) => ({
            value: o.value,
            label: o.labelEn ? pick(o.label, o.labelEn) : t(o.label),
          }))}
          onChange={onRegionChange}
          className="w-full sm:w-44"
        />
        <SelectMenu
          label={t("search.filterSector")}
          icon="ri-stack-line"
          value={sector}
          options={sectorOptions(companies).map((o) => ({
            value: o.value,
            label: o.labelEn ? pick(o.label, o.labelEn) : t(o.label),
          }))}
          onChange={onSectorChange}
          className="w-full sm:w-44"
        />
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <span className="mr-1 text-xs text-foreground-500">
          {t("search.filterRisk")}
        </span>
        {riskOptions.map((option) => {
          const active = risks.includes(option.value);
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => onToggleRisk(option.value)}
              className={`flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-1.5 text-[11px] transition-colors ${
                active
                  ? `risk-soft-${option.value} risk-border-${option.value} text-foreground-950`
                  : "border-background-200 text-foreground-500 hover:border-background-300 hover:text-foreground-800"
              }`}
            >
              <StatusDot level={option.value} size="xs" />
              {t(option.label)}
            </button>
          );
        })}
      </div>

      <div className="flex flex-wrap items-center gap-2 xl:ml-auto">
        <SelectMenu
          label={t("search.filterSort")}
          icon="ri-sort-desc"
          value={sort}
          options={sortOptions.map((o) => ({ ...o, label: t(o.label) }))}
          onChange={(value) => onSortChange(value as SortKey)}
          className="w-full sm:w-52"
        />
        <button
          type="button"
          onClick={onReset}
          disabled={activeCount === 0}
          className={`flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border px-3 py-2 text-xs transition-colors ${
            activeCount === 0
              ? "cursor-not-allowed border-background-200 text-foreground-500/50"
              : "border-background-300 text-foreground-700 hover:border-primary-400 hover:text-foreground-950"
          }`}
        >
          <i className="ri-refresh-line text-sm"></i>
          {t("search.resetFilterBtn")}
          {activeCount > 0 && (
            <span className="rounded-full bg-primary-500/15 px-1.5 font-mono text-[10px] text-primary-400">
              {activeCount}
            </span>
          )}
        </button>
      </div>
    </div>
  );
}
