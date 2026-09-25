import { http } from "@/shared/api/http";
import type { RequestGetGraph, ResponseGetGraph } from "@/shared/api/dto";

export const requestGetGraph = http.post<RequestGetGraph, ResponseGetGraph>("/graph/get");
