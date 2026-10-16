import { http } from "@/shared/api/http";
import type {
  RequestInspectData, RequestInspectCase, RequestDeletePreparation, ResponsePreparationDeletion,
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
  RequestSaveConversionPlan, RequestGetConversion, RequestImportConversion, ResponseConversionState,
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
export const requestSaveConversionPlan = http.post<RequestSaveConversionPlan, ResponseConversionState>("/data-prep/conversion/save-plan");
export const requestGetConversion = http.post<RequestGetConversion, ResponseConversionState>("/data-prep/conversion/get");
export const requestTrialConversion = http.withTimeout(60000).post<RequestGetPreparation, ResponseConversionState>("/data-prep/conversion/trial");
export const requestImportConversion = http.withTimeout(60000).post<RequestImportConversion, ResponseConversionState>("/data-prep/conversion/import");

export const requestInspectCase = http.withTimeout(120000).post<RequestInspectCase, ResponsePreparation>("/data-prep/inspect-case");

export const requestPreviewPreparationDeletion = http.post<RequestGetPreparation, ResponsePreparationDeletion>("/data-prep/delete-preview");
export const requestDeletePreparation = http.post<RequestDeletePreparation, ResponsePreparationDeletion>("/data-prep/delete");
