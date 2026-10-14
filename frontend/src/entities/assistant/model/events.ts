import type { ResponseTurnEvent } from "@/shared/api/generated/schema";
import type { Turn } from "./types";

export function applyTurnEvent(turn: Turn, event: ResponseTurnEvent): Turn {
  if (event.turnId !== turn.id || event.sequence <= turn.sequence) return turn;
  const items = [...turn.items];
  if (event.item) {
    const index = items.findIndex(item => item.id === event.item.id);
    if (index < 0) items.push(event.item);
    else items[index] = event.item;
  }
  if (event.delta) {
    const delta = event.delta;
    const index = items.findIndex(item => item.id === delta.itemId);
    if (index >= 0) {
      const item = items[index];
      if (delta.field === "text" && item.kind !== "tool_call") items[index] = { ...item, text: item.text + delta.text };
      if (delta.field === "argumentsText" && item.kind === "tool_call") items[index] = { ...item, argumentsText: item.argumentsText + delta.text };
    }
  }
  return {
    ...turn, items, sequence: event.sequence,
    status: event.status ?? turn.status, error: event.error ?? turn.error,
  };
}
