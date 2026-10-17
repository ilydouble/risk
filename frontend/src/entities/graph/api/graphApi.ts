import { http } from "@/shared/api/http";
import type { RequestGetGraph, ResponseGetGraph, RequestGetDatasetGraph, ResponseGetDatasetGraph } from "@/shared/api/generated/schema";

export const requestGetGraph = http.post<RequestGetGraph, ResponseGetGraph>("/graph/get");

export const requestGetDatasetGraph = http.post<RequestGetDatasetGraph, ResponseGetDatasetGraph>("/graph/dataset");
