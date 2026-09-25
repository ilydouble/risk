import { companies } from "./companies";

// Only these cases are provisioned in the backend; the broader catalog supports legacy demo pages.
export const demoSeedIds = [
  "C-1001",
  "C-1002",
  "C-1003",
  "C-1004",
  "C-1005",
  "C-1006",
  "C-1007",
  "C-1008",
] as const;

const ids = new Set<string>(demoSeedIds);
export const demoSeedCompanies = companies.filter((company) => ids.has(company.id));
