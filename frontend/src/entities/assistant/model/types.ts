import type { ResponseCreateTurn, ResponseListConversations } from "@/shared/api/generated/schema";

export type Turn = ResponseCreateTurn["turn"];
export type Item = Turn["items"][number];
export type Conversation = ResponseListConversations["conversations"][number];
