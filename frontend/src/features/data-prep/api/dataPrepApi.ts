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
  RequestListPreparations, RequestGetPreparation, RequestSavePreparationMapping,
  RequestSavePreparationReport, ResponseListPreparations, ResponsePreparation,
  ResponsePreparationBundle,
} from "@/shared/api/generated/schema";

export const requestInspectData = http.post<RequestInspectData, ResponseInspectData>("/data-prep/inspect");
export const requestSuggestMapping = http.withTimeout(600000).post<RequestSuggestMapping, ResponseSuggestMapping>("/data-prep/suggest-mapping");
export const requestModelDefaults = http.post<RequestModelDefaults, ResponseModelDefaults>("/data-prep/model-defaults");
export const requestTestModel = http.post<RequestTestModel, ResponseTestModel>("/data-prep/test-model");
export const requestListPreparations = http.post<RequestListPreparations, ResponseListPreparations>("/data-prep/list");
export const requestGetPreparation = http.post<RequestGetPreparation, ResponsePreparation>("/data-prep/get");
export const requestSavePreparationMapping = http.post<RequestSavePreparationMapping, ResponsePreparation>("/data-prep/save-mapping");
export const requestSavePreparationReport = http.post<RequestSavePreparationReport, ResponsePreparation>("/data-prep/save-report");
export const requestExportPreparation = http.post<RequestGetPreparation, ResponsePreparationBundle>("/data-prep/export");
