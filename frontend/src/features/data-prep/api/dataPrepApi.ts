import { http } from "@/shared/api/http";
import type {
  RequestInspectData,
  RequestModelDefaults,
  RequestSuggestMapping,
  RequestTestModel,
  ResponseInspectData,
  ResponseModelDefaults,
  ResponseSuggestMapping,
  ResponseTestModel,
} from "@/shared/api/generated/schema";

export const requestInspectData = http.post<RequestInspectData, ResponseInspectData>("/data-prep/inspect");
export const requestSuggestMapping = http.post<RequestSuggestMapping, ResponseSuggestMapping>("/data-prep/suggest-mapping");
export const requestModelDefaults = http.post<RequestModelDefaults, ResponseModelDefaults>("/data-prep/model-defaults");
export const requestTestModel = http.post<RequestTestModel, ResponseTestModel>("/data-prep/test-model");
