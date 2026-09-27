import { http } from "@/shared/api/http";
import type {
  RequestGetOverview,
  RequestGetOverviewCompany,
  RequestSearchOverviewCompany,
  ResponseGetOverview,
  ResponseGetOverviewCompany,
  ResponseSearchOverviewCompany,
} from "@/shared/api/generated/schema";

export const requestGetOverview = http.post<RequestGetOverview, ResponseGetOverview>("/overview/get");
export const requestGetOverviewCompany = http.post<RequestGetOverviewCompany, ResponseGetOverviewCompany>("/overview/get-company");
export const requestSearchOverviewCompany = http.post<RequestSearchOverviewCompany, ResponseSearchOverviewCompany>("/overview/search-companies");
