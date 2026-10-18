import { http } from "@/shared/api/http";
import type {
  RequestFinancialCatalog, ResponseFinancialCatalog,
  RequestFinancialCompanies, ResponseFinancialCompanies,
  RequestPredictFinancialCompany, ResponsePredictFinancialCompany,
  RequestPreviewFinancialInput, ResponsePreviewFinancialInput,
  RequestGetFinancialPrediction, ResponseGetFinancialPrediction,
  RequestListFinancialPredictions, ResponseListFinancialPredictions,
} from "@/shared/api/generated/schema";

export const requestCatalog = http.post<RequestFinancialCatalog, ResponseFinancialCatalog>("/decision/catalog");
export const requestCompanies = http.post<RequestFinancialCompanies, ResponseFinancialCompanies>("/decision/companies");
export const requestPredict = http.post<RequestPredictFinancialCompany, ResponsePredictFinancialCompany>("/decision/predict");
export const requestPreviewInput = http.post<RequestPreviewFinancialInput, ResponsePreviewFinancialInput>("/decision/preview-input");
export const requestGetPrediction = http.post<RequestGetFinancialPrediction, ResponseGetFinancialPrediction>("/decision/get-prediction");
export const requestListPredictions = http.post<RequestListFinancialPredictions, ResponseListFinancialPredictions>("/decision/list-predictions");
