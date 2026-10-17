import { http } from "@/shared/api/http";
import type {
  RequestScriptCatalog, ResponseScriptCatalog, ResponseScriptTaskList,
  RequestCreateScriptTask, RequestGetScriptTask, RequestSaveScriptTask,
  RequestGenerateScript, RequestRunScriptTask, RequestScriptArtifact,
  ResponseScriptTask, ResponsePreparationBundle, ResponseScriptDelivery,
} from "@/shared/api/generated/schema";

export const requestScriptCatalog = http.withTimeout(60000).post<RequestScriptCatalog, ResponseScriptCatalog>("/data-prep/script/catalog");
export const requestScriptTasks = http.post<RequestScriptCatalog, ResponseScriptTaskList>("/data-prep/script/list");
export const requestCreateScriptTask = http.withTimeout(120000).post<RequestCreateScriptTask, ResponseScriptTask>("/data-prep/script/create");
export const requestScriptTask = http.post<RequestGetScriptTask, ResponseScriptTask>("/data-prep/script/get");
export const requestSaveScriptTask = http.post<RequestSaveScriptTask, ResponseScriptTask>("/data-prep/script/save");
export const requestGenerateScript = http.withTimeout(600000).post<RequestGenerateScript, ResponseScriptTask>("/data-prep/script/generate");
export const requestRunScript = http.post<RequestRunScriptTask, ResponseScriptTask>("/data-prep/script/run");
export const requestScriptArtifact = http.withTimeout(120000).post<RequestScriptArtifact, ResponsePreparationBundle>("/data-prep/script/artifact");
export const requestDeliverScriptArtifact = http.withTimeout(120000).post<RequestScriptArtifact, ResponseScriptDelivery>("/data-prep/script/deliver");
