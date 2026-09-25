import { companies } from "@/features/demo-scenarios/model/fixtures/companies";
import { companyProfiles } from "@/features/demo-scenarios/model/fixtures/companyProfiles";
import { companyProfilesExtra } from "@/features/demo-scenarios/model/fixtures/companyProfilesExtra";
import { profilesByRisk } from "@/features/demo-scenarios/model/fixtures/profilesByRisk";
import type {
  Company,
  CompanyProfile,
  TimelineImpact,
  TimelineType,
} from "@/entities/demo/model/types";

export function findCompany(id: string | undefined): Company | undefined {
  if (!id) return undefined;
  return companies.find((company) => company.id === id);
}

export function resolveProfile(company: Company): CompanyProfile {
  return (
    companyProfiles[company.id] ??
    companyProfilesExtra[company.id] ??
    profilesByRisk[company.riskLevel]
  );
}

/** 时间线事件类型对应的图标（文案由 i18n 提供）。 */
export const timelineTypeIcon: Record<TimelineType, string> = {
  equity: "ri-exchange-line",
  legal: "ri-scales-3-line",
  address: "ri-map-pin-line",
  finance: "ri-funds-line",
  risk: "ri-alert-line",
  award: "ri-award-line",
};

export const timelineFilterOrder: TimelineType[] = [
  "equity",
  "legal",
  "finance",
  "risk",
  "award",
  "address",
];

/** 事件影响对应的语义色（文案由 i18n 提供）。 */
export const impactColorClass: Record<TimelineImpact, string> = {
  positive: "risk-text-low",
  neutral: "text-foreground-500",
  negative: "risk-text-high",
};