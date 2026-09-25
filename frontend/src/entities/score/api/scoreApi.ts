import { http } from "@/shared/api/http";
import type { RequestGetScore, ResponseGetScore } from "@/shared/api/generated/schema";

export const requestGetScore = http.post<RequestGetScore, ResponseGetScore>("/score/get");
