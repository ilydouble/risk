import assert from "node:assert/strict";
import test from "node:test";
import { graphElements, companyLink } from "../src/features/company-graph/lib/datasetGraph.ts";

const data = {
  datasetId: "dataset", demo: false, rootId: "node:A",
  nodes: [
    { id: "node:A", kind: "company", entityId: "A" },
    { id: "node:P", kind: "person", entityId: "P" },
    { id: "group:1", kind: "hyperedge" }, { id: "event:1", kind: "event" },
  ],
  edges: [
    { id: "edge:1", source: "node:A", target: "node:P", label: "owns" },
    { id: "edge:2", source: "node:A", target: "node:P", label: "owns" },
    { id: "edge:3", source: "node:P", target: "node:A", label: "owns" },
    { id: "group:1:0", source: "group:1", target: "node:A", label: "group" },
    { id: "event:1:0", source: "event:1", target: "node:A", label: "event" },
  ],
};

test("preserves person, group, event and parallel/directional links", () => {
  assert.deepEqual(graphElements(data), { nodes: data.nodes, edges: data.edges });
  assert.equal(graphElements(data, "owns").edges.length, 3);
  assert.deepEqual(graphElements(data, "missing").nodes, [data.nodes[0]]);
  assert.deepEqual(graphElements(null), { nodes: [], edges: [] });
});
test("only actual companies get a scoped company details link", () => {
  assert.equal(companyLink(data, data.nodes[0]), "/company/dataset/A?source=uploaded");
  for (const node of data.nodes.slice(1)) assert.equal(companyLink(data, node), null);
  assert.equal(companyLink({ ...data, datasetId: "other" }, data.nodes[0]), "/company/other/A?source=uploaded");
});
