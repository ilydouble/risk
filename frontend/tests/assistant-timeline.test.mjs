import assert from "node:assert/strict";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";
import { MemoryRouter } from "react-router-dom";

test("Turn rendering groups consecutive process items without changing order", async () => {
  const server = await createServer({
    root: fileURLToPath(new URL("../", import.meta.url)),
    server: { middlewareMode: true, ws: false, watch: null },
    appType: "custom",
  });
  try {
    await server.ssrLoadModule("/src/shared/config/i18n/index.ts");
    const { TurnTimeline } = await server.ssrLoadModule("/src/pages/chat/ui/TurnTimeline.tsx");
    const { formatTurnDuration } = await server.ssrLoadModule("/src/pages/chat/model/duration.ts");
    assert.equal(formatTurnDuration(36099, false), "36s");
    assert.equal(formatTurnDuration(364000, false), "6分 4秒");
    assert.equal(formatTurnDuration(3600000, true), "1h 0m 0s");
    const { ToolItemView } = await server.ssrLoadModule("/src/pages/chat/ui/ToolItemView.tsx");
    const graphTool = { id: "g", kind: "tool_call", status: "completed", toolCallId: "call", name: "show_company_graph", argumentsText: "{}", result: null,
      graph: { kind: "company_graph", companyId: "C-1001", depth: 2, lang: "zh", title: "Demo company", summary: { nodeCount: 15, edgeCount: 14 }, demo: true } };
    const card = renderToStaticMarkup(createElement(ToolItemView, { item: graphTool }));
    assert(!card.includes("Demo company")); // Generic cards do not select business renderers.
    const slotted = renderToStaticMarkup(createElement(ToolItemView, { item: graphTool }, createElement("button", null, "INTERACTION")));
    assert(slotted.indexOf("INTERACTION") > slotted.indexOf("</details>"));
    const { TurnProcess } = await server.ssrLoadModule("/src/pages/chat/ui/TurnProcess.tsx");
    const graphProcess = renderToStaticMarkup(createElement(TurnProcess, { items: [graphTool], status: "running" }));
    assert(graphProcess.includes("Demo company") && graphProcess.includes("样例数据"));
    assert(!graphProcess.includes("查看图谱") && !graphProcess.includes('role="dialog"'));
    assert(!renderToStaticMarkup(createElement(TurnProcess, { items: [{ ...graphTool, status: "failed" }], status: "failed" })).includes("Demo company"));
    const preparationTool = { id: "prep", kind: "tool_call", status: "completed", toolCallId: "prep",
      name: "preparation_trial", argumentsText: "{}", result: [{ json: { preparationId: "case-1" } }] };
    const preparation = renderToStaticMarkup(createElement(MemoryRouter,
      { initialEntries: ["/chat?conversation=conversation-1"] },
      createElement(TurnProcess, { items: [preparationTool], status: "running" })));
    assert(preparation.includes("preparation_trial"));
    assert(!preparation.includes("preparation=case-1") && !preparation.includes("导入入口"));
    const { segmentTurnItems } = await server.ssrLoadModule("/src/pages/chat/model/timeline.ts");
    const items = [
      { id: "u", kind: "user_message", text: "USER_REQUEST", status: "completed" },
      { id: "a", kind: "agent_message", text: "BEFORE_TOOL", status: "completed" },
      { id: "t", kind: "tool_call", name: "TOOL_MARKER", toolCallId: "call", argumentsText: "{}", status: "completed" },
      { id: "b", kind: "agent_message", text: "BETWEEN_STEPS", status: "completed" },
      { id: "r", kind: "reasoning", text: "REASONING_MARKER", status: "completed" },
      { id: "c", kind: "agent_message", text: "FINAL_ANSWER", status: "completed" },
    ];
    for (const status of ["running", "completed"]) {
      const turn = { id: "turn", conversationId: "conversation", status, model: "test", requestId: "test", items, elapsedMs: 12000, durationMs: status === "running" ? null : 36000 };
      const html = renderToStaticMarkup(createElement(TurnTimeline, { turn }));
      const markers = ["USER_REQUEST", "BEFORE_TOOL", "TOOL_MARKER", "BETWEEN_STEPS", "REASONING_MARKER", "FINAL_ANSWER"];
      const positions = markers.map(marker => html.indexOf(marker));
      assert(positions.every(position => position >= 0));
      assert.deepEqual(positions, [...positions].sort((a, b) => a - b));
      assert.equal((html.match(/aria-expanded=/g) ?? []).length, 3);
      assert(html.includes("<hr"));
      assert(html.indexOf("USER_REQUEST") < html.indexOf("aria-expanded="));
      const detailsId = html.match(/aria-controls="([^"]+)"/)[1];
      assert(html.indexOf("USER_REQUEST") < html.indexOf(`id="${detailsId}"`));
      assert.equal((html.match(/USER_REQUEST/g) ?? []).length, 1);
      assert(html.includes(status === "running" ? "已执行 12s" : "执行了 36s"));
      // Both process segments have a following message, even while the Turn is running.
      assert.equal((html.match(/aria-expanded="false"/g) ?? []).length, status === "running" ? 2 : 3);
    }
    const extraTool = { ...items[2], id: "t2", toolCallId: "call-2" };
    const first = segmentTurnItems(items.slice(0, 3));
    const appended = segmentTurnItems([...items.slice(0, 3), extraTool, items[4]]);
    assert.deepEqual(appended.map(block => block.kind), ["message", "message", "process"]);
    assert.equal(appended[2].id, first[2].id);
    assert.deepEqual(appended[2].items.map(item => item.id), ["t", "t2", "r"]);
    assert.equal(first[2].items.length, 1);
    assert.deepEqual(segmentTurnItems([]), []);
    assert(segmentTurnItems([items[0], items[1]]).every(block => block.kind === "message"));
    const separated = segmentTurnItems([...items.slice(0, 3), items[3], extraTool]);
    assert.deepEqual(separated.map(block => block.kind), ["message", "message", "process", "message", "process"]);
    assert.notEqual(separated[2].id, separated[4].id);
    for (const status of ["running", "completed", "cancelled", "failed", "interrupted"]) {
      const turn = { id: "tail", status, model: "test", requestId: "test", items: items.slice(0, -1) };
      const html = renderToStaticMarkup(createElement(TurnTimeline, { turn }));
      const expanded = [...html.matchAll(/aria-expanded="(true|false)"/g)].map(match => match[1]);
      assert.deepEqual(expanded, [status === "running" ? "true" : "false", "false", status === "running" ? "true" : "false"]);
    }
  } finally {
    await server.close();
  }
});
