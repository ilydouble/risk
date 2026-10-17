import { http } from "@/shared/api/http";
import type { RequestModelDefaults, ResponseModelDefaults, RequestTestModel, ResponseTestModel } from "@/shared/api/generated/schema";

export const requestModelDefaults = http.post<RequestModelDefaults, ResponseModelDefaults>("/assistant/model-defaults");
export const requestTestModel = http.post<RequestTestModel, ResponseTestModel>("/assistant/test-model");
