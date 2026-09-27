import i18n from "@/shared/config/i18n";
import type { components, RequestSearchOverviewCompany } from "@/shared/api/generated/schema";

export type OverviewSampleCompany = components["schemas"]["OverviewSampleCompanyDTO"];
export type SearchCategory = RequestSearchOverviewCompany["category"];
export type SearchSort = RequestSearchOverviewCompany["sort"];

export function exportOverviewSamplesCsv(list: OverviewSampleCompany[]): void {
  const header = [
    "UEN",
    i18n.t("search.csvName"),
    i18n.t("search.csvStatus"),
    i18n.t("search.csvCategory"),
    i18n.t("search.csvAge"),
    "SSIC",
    i18n.t("search.csvRelations"),
  ];
  const rows = list.map((company) => [
    company.companyId,
    company.name,
    company.status,
    i18n.t(`search.category.${company.labelCategory}`),
    company.ageYears?.toFixed(1) ?? "",
    company.industryCode ?? "",
    String(company.relationCount),
  ]);
  const csv = [header, ...rows]
    .map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(","))
    .join("\n");
  const blob = new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = i18n.t("search.csvFileName");
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}
