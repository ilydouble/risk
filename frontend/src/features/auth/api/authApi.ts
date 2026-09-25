import { http } from "@/shared/api/http";
import type {
  RequestLogin, RequestLogout, RequestMe, RequestRegister,
  ResponseLogin, ResponseLogout, ResponseMe, ResponseRegister,
} from "@/shared/api/generated/schema";

export const requestRegister = http.post<RequestRegister, ResponseRegister>("/auth/register");
export const requestLogin = http.post<RequestLogin, ResponseLogin>("/auth/login");
export const requestLogout = http.post<RequestLogout, ResponseLogout>("/auth/logout");
export const requestMe = http.post<RequestMe, ResponseMe>("/auth/me");
