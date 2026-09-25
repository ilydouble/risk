import i18n from "@/i18n";
import { companies } from "@/mocks/companies";
import type { Company, RiskLevel } from "@/types";

export type SortKey = "score_desc" | "score_asc" | "dp_desc" | "recent";

export interface SortOption {
  value: SortKey;
  label: string;
}

const RISK_LABEL: Record<RiskLevel, string> = {
  low: "risk.low",
  medium: "risk.medium",
  high: "risk.high",
};

function uniqueSorted(values: string[]): string[] {
  return Array.from(new Set(values)).sort((a, b) => a.localeCompare(b, "zh-CN"));
}

export interface FilterOption {
  value: string;
  label: string;
  labelEn?: string;
}

export const regionOptions: FilterOption[] = [
  { value: "all", label: "search.allCountries" },
  ...uniqueSorted(companies.map((c) => c.region)).map((region) => ({
    value: region,
    label: region,
    labelEn: companies.find((c) => c.region === region)?.regionEn,
  })),
];

export const sectorOptions: FilterOption[] = [
  { value: "all", label: "search.allSectors" },
  ...uniqueSorted(companies.map((c) => c.sector)).map((sector) => ({
    value: sector,
    label: sector,
    labelEn: companies.find((c) => c.sector === sector)?.sectorEn,
  })),
];

export const sortOptions: SortOption[] = [
  { value: "score_desc", label: "search.sortScoreDesc" },
  { value: "score_asc", label: "search.sortScoreAsc" },
  { value: "dp_desc", label: "search.sortDpDesc" },
  { value: "recent", label: "search.sortRecent" },
];

export const riskOptions: { value: RiskLevel; label: string }[] = [
  { value: "low", label: "risk.low" },
  { value: "medium", label: "risk.medium" },
  { value: "high", label: "risk.high" },
];

export interface FilterState {
  keyword: string;
  region: string;
  sector: string;
  risks: RiskLevel[];
  sort: SortKey;
}

export type GroupKey = "region" | "sector";

export interface CompanyGroup {
  key: string;
  label: string;
  labelEn?: string;
  companies: Company[];
  count: number;
  avgScore: number;
  avgDefaultProb: number;
  highRiskShare: number;
  riskCounts: Record<RiskLevel, number>;
}

export function groupCompanies(
  list: Company[],
  groupKey: GroupKey,
): CompanyGroup[] {
  const buckets = new Map<string, Company[]>();

  list.forEach((company) => {
    const key = groupKey === "region" ? company.region : company.sector;
    const bucket = buckets.get(key) ?? [];
    bucket.push(company);
    buckets.set(key, bucket);
  });

  const groups: CompanyGroup[] = [];
  buckets.forEach((companies, key) => {
    const count = companies.length;
    const labelEn = groupKey === "region" ? companies[0].regionEn : companies[0].sectorEn;
    const avgScore = Math.round(
      companies.reduce((sum, c) => sum + c.creditScore, 0) / count,
    );
    const avgDefaultProb =
      companies.reduce((sum, c) => sum + c.defaultProb, 0) / count;
    const riskCounts: Record<RiskLevel, number> = { low: 0, medium: 0, high: 0 };
    companies.forEach((c) => {
      riskCounts[c.riskLevel] += 1;
    });

    groups.push({
      key,
      label: key,
      labelEn,
      companies: [...companies].sort((a, b) => b.creditScore - a.creditScore),
      count,
      avgScore,
      avgDefaultProb,
      highRiskShare: Math.round((riskCounts.high / count) * 100),
      riskCounts,
    });
  });

  return groups.sort(
    (a, b) => b.count - a.count || a.label.localeCompare(b.label, "zh-CN"),
  );
}

export function filterCompanies(state: FilterState): Company[] {
  const keyword = state.keyword.trim().toLowerCase();

  const matched = companies.filter((company) => {
    const hitKeyword =
      keyword.length === 0 ||
      company.nameCn.toLowerCase().includes(keyword) ||
      company.nameEn.toLowerCase().includes(keyword) ||
      company.regNo.toLowerCase().includes(keyword);

    const hitRegion = state.region === "all" || company.region === state.region;
    const hitSector = state.sector === "all" || company.sector === state.sector;
    const hitRisk =
      state.risks.length === 0 || state.risks.includes(company.riskLevel);

    return hitKeyword && hitRegion && hitSector && hitRisk;
  });

  const sorted = [...matched];
  switch (state.sort) {
    case "score_asc":
      sorted.sort((a, b) => a.creditScore - b.creditScore);
      break;
    case "dp_desc":
      sorted.sort((a, b) => b.defaultProb - a.defaultProb);
      break;
    case "recent":
      sorted.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
      break;
    default:
      sorted.sort((a, b) => b.creditScore - a.creditScore);
  }
  return sorted;
}

export function riskLabel(level: RiskLevel): string {
  return RISK_LABEL[level];
}

export function exportCompaniesCsv(list: Company[]): void {
  const header = [
    i18n.t("search.csvCompanyId"),
    i18n.t("search.csvNameCn"),
    i18n.t("search.csvNameEn"),
    i18n.t("search.csvRegNo"),
    i18n.t("search.csvCountry"),
    i18n.t("search.csvIndustry"),
    i18n.t("search.csvScore"),
    i18n.t("search.csvRisk"),
    i18n.t("search.csvPd"),
    i18n.t("search.csvUpdatedAt"),
  ];
  const rows = list.map((c) => [
    c.id,
    c.nameCn,
    c.nameEn,
    c.regNo,
    c.country,
    c.industry,
    String(c.creditScore),
    i18n.t(riskLabel(c.riskLevel)),
    c.defaultProb.toFixed(1),
    c.updatedAt,
  ]);
  const csv = [header, ...rows]
    .map((row) =>
      row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(","),
    )
    .join("\n");

  const blob = new Blob([`\uFEFF${csv}`], {
    type: "text/csv;charset=utf-8;",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = i18n.t("search.csvFileName");
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}