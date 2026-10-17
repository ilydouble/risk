import type { Item } from "@/entities/assistant/model/types";

export type ProcessItem = Extract<Item, { kind: "reasoning" | "tool_call" }>;
type MessageItem = Extract<Item, { kind: "user_message" | "agent_message" }>;
type TimelineBlock =
  | { kind: "message"; id: string; item: MessageItem }
  | { kind: "process"; id: string; items: ProcessItem[] };

export function segmentTurnItems(items: readonly Item[]): TimelineBlock[] {
  const blocks: TimelineBlock[] = [];
  for (const item of items) {
    if (item.kind === "user_message" || item.kind === "agent_message") {
      blocks.push({ kind: "message", id: item.id, item });
    } else {
      const previous = blocks.at(-1);
      if (previous?.kind === "process") previous.items.push(item);
      // Keep the first Item ID when tokens or subsequent process Items arrive.
      else blocks.push({ kind: "process", id: item.id, items: [item] });
    }
  }
  return blocks;
}
