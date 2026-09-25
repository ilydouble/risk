import { useEffect, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { isHttpClientError } from "@stellarmesh/sdk";
import * as AuthApi from "@/features/auth/api/authApi";
import { AuthUserContext } from "@/features/auth/model/AuthContext";
import type { ResponseMe } from "@/shared/api/dto";

export default function AuthGate() {
  const navigate = useNavigate();
  const location = useLocation();
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [user, setUser] = useState<ResponseMe | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    AuthApi.requestMe({})
      .then((identity) => { if (active) { setUser(identity); setState("ready"); } })
      .catch((error: unknown) => {
        if (!active) return;
        if (isHttpClientError(error) && error.status === 401) {
          navigate("/login", { replace: true, state: { from: location.pathname + location.search } });
        } else {
          setState("error");
        }
      });
    return () => { active = false; };
  }, [attempt, location.pathname, location.search, navigate]);

  if (state === "loading") return <div className="flex min-h-screen items-center justify-center bg-background-50 text-foreground-700">正在验证会话…</div>;
  if (state === "error") return <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-background-50 text-foreground-700"><p>会话服务暂时不可用</p><button type="button" className="rounded-md bg-primary-500 px-4 py-2 text-background-50" onClick={() => { setState("loading"); setAttempt((value) => value + 1); }}>重试</button></div>;
  return <AuthUserContext.Provider value={user}><Outlet /></AuthUserContext.Provider>;
}
