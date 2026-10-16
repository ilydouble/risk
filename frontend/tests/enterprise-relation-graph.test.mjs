import assert from "node:assert/strict";
import { test } from "node:test";
import { buildRelationGraph, companyGraphId, GRAPH_NODE_LIMIT, GROUP_MEMBER_LIMIT } from "../src/features/enterprise-browser/lib/relationGraph.ts";

function company(related) {
  return { company: { nodeId: "001", snapshot: "import", data: { name: "Company 001" } }, related };
}
const edge = (sequence, source = "001", target = "002", snapshot = "import") => ({ sequence, source, target, snapshot, kind: "edge", members: [], data: { relation: "EQUITY", weight: 1 } });
const group = (sequence, members) => ({ sequence, kind: "hyperedge", snapshot: "import", members, data: { kind: "director_group" } });

test("preserves directed evidence, keeps ID namespaces distinct and does not create company cliques", () => {
  const input = company({ edge: { items: [edge(1, "002", "001")] }, hyperedge: { items: [group(2, ["001", "002", "group:2"])] } });
  const graph = buildRelationGraph(input);
  assert.equal(graph.edges[0].source, companyGraphId("002"));
  assert.equal(graph.edges[0].target, companyGraphId("001"));
  assert.equal(graph.groups.size, 1);
  assert.equal(graph.companies.size, 3);
  assert.equal(graph.edges.length, 4);
  assert.ok(graph.edges.slice(1).every(e => e.source === "group:2" && e.directed === false));
  assert.equal(new Set(graph.nodes.map(n => n.id)).size, graph.nodes.length);
  assert.equal(graph.evidence.get("edge:1"), input.related.edge.items[0]);
});

test("caps large groups and always includes the focal enterprise, retaining full evidence", () => {
  const members = [...Array.from({ length: 5000 }, (_, i) => `other-${i}`), "001"];
  const record = group(3, members);
  const graph = buildRelationGraph(company({ hyperedge: { items: [record] } }));
  assert.equal(graph.companies.size, GROUP_MEMBER_LIMIT);
  assert.equal(graph.omittedMembers, members.length - GROUP_MEMBER_LIMIT);
  assert.ok(graph.edges.some(e => e.target === companyGraphId("001")));
  assert.equal(graph.groups.get("group:3").members.length, members.length);
  const many = buildRelationGraph(company({ hyperedge: { items: Array.from({ length: 20 }, (_, i) => group(i, ["001", ...members.map(m => `${i}-${m}`)])) } }));
  assert.ok(many.nodes.length <= GRAPH_NODE_LIMIT);
  assert.ok(many.omittedRecords > 0 || many.omittedMembers > 0);
});

test("filters relation kinds and excludes unrelated or cross-snapshot records", () => {
  const input = company({ edge: { items: [edge(1), edge(2, "001", "003", "test"), edge(3, "003", "004")] }, hyperedge: { items: [group(4, ["001", "002"])] } });
  assert.equal(buildRelationGraph(input, "EQUITY").edges.length, 1);
  assert.equal(buildRelationGraph(input, "director_group").groups.size, 1);
  assert.equal(buildRelationGraph(company({})).nodes.length, 1);
});
