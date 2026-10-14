import { http } from "@/shared/api/http";
import type {
  RequestAskData, ResponseAskData, RequestDataQACatalog, ResponseDataQACatalog,
} from "@/shared/api/generated/schema";

export const requestDataQACatalog = http.post<RequestDataQACatalog, ResponseDataQACatalog>(
  "/data-qa/catalog",
);
export const requestAskData = http.withTimeout(70000).post<RequestAskData, ResponseAskData>(
  "/data-qa/ask",
);
