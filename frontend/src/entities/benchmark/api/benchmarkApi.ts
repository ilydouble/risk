import { http } from "@/shared/api/http";
import type {
  RequestEvaluationBenchmark,
  RequestExplainBenchmark,
  RequestGetBenchmark,
  RequestGraphBenchmark,
  RequestModelCardBenchmark,
  RequestPredictBenchmark,
  RequestSearchBenchmark,
  ResponseEvaluationBenchmark,
  ResponseExplainBenchmark,
  ResponseGetBenchmark,
  ResponseGraphBenchmark,
  ResponseModelCardBenchmark,
  ResponsePredictBenchmark,
  ResponseSearchBenchmark,
} from "@/shared/api/generated/schema";

export const requestSearchBenchmark = http.post<RequestSearchBenchmark, ResponseSearchBenchmark>("/benchmark/search");
export const requestGetBenchmark = http.post<RequestGetBenchmark, ResponseGetBenchmark>("/benchmark/get");
export const requestPredictBenchmark = http.post<RequestPredictBenchmark, ResponsePredictBenchmark>("/benchmark/predict");
export const requestExplainBenchmark = http.post<RequestExplainBenchmark, ResponseExplainBenchmark>("/benchmark/explain");
export const requestGraphBenchmark = http.post<RequestGraphBenchmark, ResponseGraphBenchmark>("/benchmark/graph");
export const requestEvaluationBenchmark = http.post<RequestEvaluationBenchmark, ResponseEvaluationBenchmark>("/benchmark/evaluation");
export const requestModelCardBenchmark = http.post<RequestModelCardBenchmark, ResponseModelCardBenchmark>("/benchmark/model-card");
