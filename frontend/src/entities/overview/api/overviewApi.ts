import { http } from "@/shared/api/http";
import type {
  RequestGetOverview,
  ResponseGetOverview,
} from "@/shared/api/generated/schema";

export const requestGetOverview = http.post<RequestGetOverview, ResponseGetOverview>("/overview/get");
