import { http } from "@/shared/api/http";
import type { RequestGetScore, ResponseGetScore } from "@/shared/api/dto";

export const requestGetScore = http.post<RequestGetScore, ResponseGetScore>("/score/get");
