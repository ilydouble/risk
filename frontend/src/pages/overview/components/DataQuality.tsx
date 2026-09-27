import { useTranslation } from "react-i18next";
import type { components } from "@/shared/api/generated/schema";

type OverviewQualityDTO = components["schemas"]["OverviewQualityDTO"];
const percent = (value: number) => `${(value * 100).toFixed(2)}%`;

export default function DataQuality({ quality }: { quality: OverviewQualityDTO }) {
  const { t } = useTranslation();
  const items = [
    ["labeledRate", percent(quality.labeledRate)],
    ["distressRate", percent(quality.distressRateWithinLabeled)],
    ["edgeCoverage", percent(quality.ordinaryEdgeCoverageWithinLabeled)],
    ["capitalCoverage", percent(quality.capitalCoverage)],
    ["litigationRows", quality.litigationRows.toLocaleString()],
  ];
  return <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-5">{items.map(([key, value]) => <div key={key} className="rounded-md bg-background-50 px-3 py-3"><p className="text-[11px] text-foreground-500">{t(`overview.quality.${key}`)}</p><p className="mt-1 font-mono text-lg font-semibold text-foreground-950">{value}</p></div>)}</div>;
}
