import { http } from "@/shared/api/http";
import type {
  RequestInspectData,
  RequestSuggestMapping,
  ResponseInspectData,
  ResponseSuggestMapping,
} from "@/shared/api/generated/schema";

export const requestInspectData = http.post<RequestInspectData, ResponseInspectData>("/data-prep/inspect");
export const requestSuggestMapping = http.post<RequestSuggestMapping, ResponseSuggestMapping>("/data-prep/suggest-mapping");
