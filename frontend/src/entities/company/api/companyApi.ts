import { http } from "@/shared/api/http";
import type {
  RequestGetCompany, RequestSearchCompany, ResponseGetCompany, ResponseSearchCompany,
} from "@/shared/api/dto";

export const requestSearchCompany = http.post<RequestSearchCompany, ResponseSearchCompany>("/company/search");
export const requestGetCompany = http.post<RequestGetCompany, ResponseGetCompany>("/company/get");
