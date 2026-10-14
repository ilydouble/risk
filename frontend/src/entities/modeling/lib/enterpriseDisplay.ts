import type { components } from "@/shared/api/generated/schema";
type EnterpriseRecordDTO = components["schemas"]["EnterpriseRecordDTO"];

export function displayEnterpriseValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}
export function enterpriseName(row: EnterpriseRecordDTO): string {
  return typeof row.data.name === "string" && row.data.name.trim() ? row.data.name : row.nodeId ?? "未命名企业";
}
export function enterpriseLink(dataset: string, node: string): string {
  return `/company/${encodeURIComponent(dataset)}/${encodeURIComponent(node)}?source=uploaded`;
}
