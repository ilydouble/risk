import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import * as AuthApi from "@/features/auth/api/authApi";
import { handleApiError } from "@/shared/api/http";
import { useLang } from "@/shared/lib/useLang";

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const navigationState = location.state as { from?: string; registeredUsername?: string } | null;
  const { isEn } = useLang();
  const [username, setUsername] = useState(navigationState?.registeredUsername ?? "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      await AuthApi.requestLogin({ username, password });
      const from = navigationState?.from;
      navigate(from?.startsWith("/") ? from : "/", { replace: true });
    } catch (failure) {
      setError(handleApiError(failure, { AUTH_INVALID_CREDENTIALS: isEn ? "Invalid credentials" : "账号或密码错误" }));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background-50 px-4 text-foreground-900">
      <motion.form initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} onSubmit={submit} className="w-full max-w-sm rounded-xl border border-background-300 bg-background-100 p-8">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-primary-400">Risk Workbench</p>
        <h1 className="mt-3 font-heading text-2xl font-semibold">{isEn ? "Sign in" : "登录风控工作台"}</h1>
        <p className="mt-2 text-xs text-foreground-500">{isEn ? "Demo data only" : "演示环境 · 数据仅供展示"}</p>
        {navigationState?.registeredUsername && <p role="status" className="mt-4 rounded-md border border-primary-500/30 bg-primary-500/10 px-3 py-2 text-xs text-primary-400">{isEn ? "Account created. Sign in to continue." : "账号创建成功，请登录。"}</p>}
        <label className="mt-7 block text-xs text-foreground-700">{isEn ? "Username" : "用户名"}<input autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} className="mt-2 w-full rounded-md border border-background-300 bg-background-50 px-3 py-2 text-sm outline-none focus:border-primary-400" /></label>
        <label className="mt-4 block text-xs text-foreground-700">{isEn ? "Password" : "密码"}<input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} className="mt-2 w-full rounded-md border border-background-300 bg-background-50 px-3 py-2 text-sm outline-none focus:border-primary-400" /></label>
        {error && <p role="alert" className="mt-3 text-xs text-red-500">{error}</p>}
        <button type="submit" disabled={loading} className="mt-6 w-full rounded-md bg-primary-500 px-4 py-2.5 text-sm font-medium text-background-50 disabled:opacity-50">{loading ? "…" : isEn ? "Sign in" : "登录"}</button>
        <p className="mt-5 text-center text-xs text-foreground-500">{isEn ? "No account yet?" : "还没有账号？"} <Link to="/register" state={{ from: navigationState?.from }} className="text-primary-400 hover:underline">{isEn ? "Create one" : "立即注册"}</Link></p>
      </motion.form>
    </div>
  );
}
