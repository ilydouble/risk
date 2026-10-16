import type { ResponseEnterpriseCompany } from "@/shared/api/generated/schema";
import type { GraphViewEdge, GraphViewNode } from "@/shared/ui/graph/types";

export type EnterpriseRelationRecord = ResponseEnterpriseCompany["company"];

export const GRAPH_NODE_LIMIT = 100;
export const GROUP_MEMBER_LIMIT = 12;
export const relationLabel = (kind: string) => ({ SAME_ADDRESS: "同注册地址", EQUITY: "股权关系", PREVNAME: "曾用名关联", SAME_NAME: "同名关系", sic_section: "同行业群组", postcode_area: "同邮区群组", director_group: "共同董事群组" } as Record<string, string>)[kind] ?? kind;
export const relationType = (record: EnterpriseRelationRecord) => String(record.data[record.kind === "hyperedge" ? "kind" : "relation"] ?? record.kind);
export const companyGraphId = (id: string) => `company:${id}`;

export function buildRelationGraph(data: ResponseEnterpriseCompany, filter = "all") {
  const centerId = companyGraphId(data.company.nodeId!);
  const nodes: GraphViewNode[] = [{ id: centerId, label: String(data.company.data.name || data.company.nodeId), size: 48 }];
  const edges: GraphViewEdge[] = [];
  const companies = new Map([[centerId, data.company.nodeId!]]);
  const groups = new Map<string, EnterpriseRelationRecord>();
  const evidence = new Map<string, EnterpriseRelationRecord>();
  let omittedMembers = 0;
  let omittedRecords = 0;
  const records = [...(data.related.edge?.items ?? []), ...(data.related.hyperedge?.items ?? [])]
    .filter(record => record.snapshot === data.company.snapshot && (filter === "all" || relationType(record) === filter));
  function addCompany(id: string) {
    const key = companyGraphId(id);
    if (!companies.has(key)) {
      nodes.push({ id: key, label: id });
      companies.set(key, id);
    }
    return key;
  }
  for (const record of records) {
    const label = relationLabel(relationType(record));
    if (record.kind === "edge") {
      if (!record.source || !record.target || ![record.source, record.target].includes(data.company.nodeId!)) continue;
      const newIds = new Set([record.source, record.target].filter(id => !companies.has(companyGraphId(id))));
      if (nodes.length + newIds.size > GRAPH_NODE_LIMIT) { omittedRecords++; continue; }
      const id = `edge:${record.sequence}`;
      edges.push({ id, source: addCompany(record.source), target: addCompany(record.target), label });
      evidence.set(id, record);
    } else if (record.kind === "hyperedge" && record.members.includes(data.company.nodeId!)) {
      if (nodes.length >= GRAPH_NODE_LIMIT) { omittedRecords++; continue; }
      const groupId = `group:${record.sequence}`;
      nodes.push({ id: groupId, label: `${label} · ${record.members.length}家`, size: 24 });
      groups.set(groupId, record);
      // Keep the focal enterprise even when it is near the end of a very large source group.
      const members = [data.company.nodeId!, ...record.members.filter(id => id !== data.company.nodeId)];
      let shown = 0;
      for (const member of members) {
        if (shown >= GROUP_MEMBER_LIMIT || (!companies.has(companyGraphId(member)) && nodes.length >= GRAPH_NODE_LIMIT)) continue;
        const id = `membership:${record.sequence}:${shown++}`;
        edges.push({ id, source: groupId, target: addCompany(member), directed: false, dashed: true });
        evidence.set(id, record);
      }
      omittedMembers += record.members.length - shown;
    }
  }
  return { nodes, edges, centerId, companies, groups, evidence, omittedMembers, omittedRecords };
}
