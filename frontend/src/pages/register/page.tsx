import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import * as AuthApi from "@/features/auth/api/authApi";
import { handleApiError } from "@/shared/api/http";
import { useLang } from "@/shared/lib/useLang";

const inputClassName =
  "mt-2 w-full rounded-md border border-background-300 bg-background-50 px-3 py-2 text-sm outline-none focus:border-primary-400";

export default function RegisterPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from;
  const { isEn } = useLang();
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (loading) return;
    if (password !== confirmation) {
      setError(isEn ? "Passwords do not match" : "两次输入的密码不一致");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const account = await AuthApi.requestRegister({ username, displayName, password });
      navigate("/login", {
        replace: true,
        state: { from, registeredUsername: account.username },
      });
    } catch (failure) {
      setError(handleApiError(failure, {
        AUTH_USERNAME_TAKEN: isEn ? "Username is already taken" : "用户名已被使用",
        REQUEST_INVALID: isEn ? "Check the account details and try again" : "请检查注册信息后重试",
      }));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background-50 px-4 text-foreground-900">
      <motion.form
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        onSubmit={submit}
        className="w-full max-w-sm rounded-xl border border-background-300 bg-background-100 p-8"
      >
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-primary-400">Risk Workbench</p>
        <h1 className="mt-3 font-heading text-2xl font-semibold">
          {isEn ? "Create account" : "注册风控工作台"}
        </h1>
        <p className="mt-2 text-xs text-foreground-500">
          {isEn ? "Demo workspace · sample data only" : "演示环境 · 数据仅供展示"}
        </p>

        <label className="mt-7 block text-xs text-foreground-700">
          {isEn ? "Username" : "用户名"}
          <input
            required
            autoComplete="username"
            pattern="[A-Za-z0-9._-]{3,32}"
            title={isEn ? "3–32 letters, numbers, dots, underscores or hyphens" : "3–32 位字母、数字、点、下划线或连字符"}
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            className={inputClassName}
          />
        </label>
        <label className="mt-4 block text-xs text-foreground-700">
          {isEn ? "Display name" : "显示名称"}
          <input
            required
            maxLength={128}
            autoComplete="name"
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            className={inputClassName}
          />
        </label>
        <label className="mt-4 block text-xs text-foreground-700">
          {isEn ? "Password (8–128 characters)" : "密码（8–128 位）"}
          <input
            required
            type="password"
            minLength={8}
            maxLength={128}
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className={inputClassName}
          />
        </label>
        <label className="mt-4 block text-xs text-foreground-700">
          {isEn ? "Confirm password" : "确认密码"}
          <input
            required
            type="password"
            minLength={8}
            maxLength={128}
            autoComplete="new-password"
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
            className={inputClassName}
          />
        </label>
        {error && <p role="alert" className="mt-3 text-xs text-red-500">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="mt-6 w-full rounded-md bg-primary-500 px-4 py-2.5 text-sm font-medium text-background-50 disabled:opacity-50"
        >
          {loading ? "…" : isEn ? "Create account" : "注册"}
        </button>
        <p className="mt-5 text-center text-xs text-foreground-500">
          {isEn ? "Already have an account?" : "已有账号？"}{" "}
          <Link to="/login" state={{ from }} className="text-primary-400 hover:underline">
            {isEn ? "Sign in" : "返回登录"}
          </Link>
        </p>
      </motion.form>
    </div>
  );
}
