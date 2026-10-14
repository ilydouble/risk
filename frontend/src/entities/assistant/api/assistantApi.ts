import { http } from "@/shared/api/http";
import type {
  RequestCreateConversation, ResponseCreateConversation,
  RequestListConversations, ResponseListConversations,
  RequestGetConversation, ResponseGetConversation,
  RequestCreateTurn, ResponseCreateTurn,
  RequestCancelTurn, ResponseCancelTurn,
} from "@/shared/api/generated/schema";

export const requestCreateConversation = http.post<RequestCreateConversation, ResponseCreateConversation>("/assistant/conversations/create");
export const requestListConversations = http.post<RequestListConversations, ResponseListConversations>("/assistant/conversations/list");
export const requestGetConversation = http.post<RequestGetConversation, ResponseGetConversation>("/assistant/conversations/get");
export const requestCreateTurn = http.post<RequestCreateTurn, ResponseCreateTurn>("/assistant/turns/create");
export const requestCancelTurn = http.post<RequestCancelTurn, ResponseCancelTurn>("/assistant/turns/cancel");
