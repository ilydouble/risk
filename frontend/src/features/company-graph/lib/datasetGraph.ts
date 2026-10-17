import type { ResponseGetDatasetGraph } from "@/shared/api/generated/schema";

export function graphElements(data: ResponseGetDatasetGraph | null, filter = "all") {
  const edges = (data?.edges ?? []).filter(edge => filter === "all" || edge.label === filter);
  const visible = new Set([data?.rootId, ...edges.flatMap(edge => [edge.source, edge.target])]);
  return { edges, nodes: (data?.nodes ?? []).filter(node => visible.has(node.id)) };
}

export function companyLink(data: ResponseGetDatasetGraph, node: ResponseGetDatasetGraph["nodes"][number]) {
  if (node.kind !== "company" || !node.entityId) return null;
  return data.demo ? `/company/${encodeURIComponent(node.entityId)}`
    : `/company/${encodeURIComponent(data.datasetId)}/${encodeURIComponent(node.entityId)}?source=uploaded`;
}
