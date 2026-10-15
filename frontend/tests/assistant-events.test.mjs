import assert from "node:assert/strict";
import { test } from "node:test";
import { applyTurnEvent } from "../src/entities/assistant/model/events.ts";

const turn = { id: "turn", conversationId: "conversation", status: "running", sequence: 0, items: [] };
const event = (sequence, values) => ({ version: 1, turnId: "turn", sequence, ...values });

test("snapshot + delta replay is ordered and duplicate delivery is idempotent", () => {
  const initial = event(1, { type: "item_updated", item: { id: "answer", kind: "agent_message", status: "running", text: "你" } });
  const started = applyTurnEvent(turn, initial);
  const delta = event(2, { type: "item_delta", delta: { itemId: "answer", field: "text", text: "好" } });
  const next = applyTurnEvent(started, delta);
  assert.equal(next.items[0].text, "你好");
  assert.equal(applyTurnEvent(next, delta), next);
  assert.equal(applyTurnEvent(next, initial), next);
  assert.equal(started.items[0].text, "你");
  const done = applyTurnEvent(next, event(3, { type: "turn_completed", status: "completed" }));
  assert.equal(done.status, "completed");
});

test("tool parameter chunks and final result use the same item identity", () => {
  let value = applyTurnEvent(turn, event(1, { type: "item_updated", item: { id: "tool", kind: "tool_call", toolCallId: "call", name: "current_time", argumentsText: '{"timezone":', status: "running" } }));
  value = applyTurnEvent(value, event(2, { type: "item_delta", delta: { itemId: "tool", field: "argumentsText", text: '"UTC"}' } }));
  assert.deepEqual(JSON.parse(value.items[0].argumentsText), { timezone: "UTC" });
  value = applyTurnEvent(value, event(3, { type: "item_updated", item: { ...value.items[0], status: "completed", result: { time: "now" } } }));
  assert.equal(value.items.length, 1);
  assert.deepEqual(value.items[0].result, { time: "now" });
  assert.equal(applyTurnEvent(value, { ...event(4, { status: "failed" }), turnId: "another" }), value);
});

test("reasoning deltas and history snapshots preserve order around tools and answers", () => {
  let value = applyTurnEvent(turn, event(1, { type: "item_updated", item: { id: "reason-1", kind: "reasoning", status: "running", text: "先" } }));
  value = applyTurnEvent(value, event(2, { type: "item_delta", delta: { itemId: "reason-1", field: "text", text: "分析" } }));
  value = applyTurnEvent(value, event(3, { type: "item_updated", item: { ...value.items[0], status: "completed" } }));
  const nextItems = [
    { id: "tool", kind: "tool_call", name: "current_time", status: "completed", argumentsText: "{}", result: [] },
    { id: "reason-2", kind: "reasoning", status: "completed", text: "整理结果" },
    { id: "answer", kind: "agent_message", status: "completed", text: "回答" },
  ];
  nextItems.forEach((item, index) => { value = applyTurnEvent(value, event(4 + index, { type: "item_updated", item })); });
  assert.deepEqual(value.items.map(item => item.kind), ["reasoning", "tool_call", "reasoning", "agent_message"]);
  assert.equal(value.items[0].text, "先分析");
  assert.equal(value.items[2].text, "整理结果");
  assert.deepEqual(applyTurnEvent(value, event(6, { type: "item_updated", item: nextItems[2] })), value);
});
