import { flattenEnvelopeResponse, http as sdkHttp, isHttpClientError } from "@stellarmesh/sdk";

export const http = sdkHttp
  .withBaseURL("/api/v1")
  .withErrorCodeExtractor((data) => {
    if (typeof data !== "object" || data === null || !("internal_code" in data)) return undefined;
    const code = data.internal_code;
    return typeof code === "string" ? code : undefined;
  })
  .withResponseTransform(flattenEnvelopeResponse());

export function handleApiError(
  error: unknown,
  known: Readonly<Record<string, string>> = {},
): string {
  if (isHttpClientError(error)) {
    const code = String(error.apiCode ?? "");
    if (code in known) return known[code];
    if (code === "AUTH_SESSION_EXPIRED") {
      window.dispatchEvent(new Event("risk:session-expired"));
      return "会话已过期，请重新登录";
    }
    const message = error.status === 503 ? "服务暂时不可用，请稍后重试" : "请求失败，请重试";
    window.dispatchEvent(new CustomEvent("risk:api-error", { detail: message }));
    return message;
  }
  window.dispatchEvent(new CustomEvent("risk:api-error", { detail: "请求失败，请重试" }));
  return "请求失败，请重试";
}
