import { createContext, useContext } from "react";
import type { ResponseMe } from "@/shared/api/dto";

export const AuthUserContext = createContext<ResponseMe | null>(null);

export function useAuthUser() {
  return useContext(AuthUserContext);
}
