import { http } from "@/shared/api/http";
import type {
  RequestGetOverview,
  RequestSearchOverviewCompany,
  ResponseGetOverview,
  ResponseSearchOverviewCompany,
} from "@/shared/api/generated/schema";

export const requestGetOverview = http.post<RequestGetOverview, ResponseGetOverview>("/overview/get");
export const requestSearchOverviewCompany = http.post<RequestSearchOverviewCompany, ResponseSearchOverviewCompany>("/overview/search-companies");
