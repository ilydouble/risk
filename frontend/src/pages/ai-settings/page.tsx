import { useState } from "react";
import { Link } from "react-router-dom";
import { requestTestModel } from "@/features/data-prep/api/dataPrepApi";
import { useAiModelConfig } from "@/features/ai-model-config/model/context";
import { handleApiError } from "@/shared/api/http";

const panel = "rounded-xl border border-background-200 bg-background-100 p-5";
const button = "rounded-md bg-primary-500 px-4 py-2 text-sm text-white disabled:opacity-50";
const input = "mt-1 w-full rounded-md border border-background-300 bg-background-50 p-2 text-sm";

export default function AiSettingsPage() {
  const config = useAiModelConfig();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");

  async function test() {
    setBusy(true);
    setError("");
    setStatus("");
    try {
      const result = await requestTestModel({ connection: config.connection });
      setStatus(`连接成功：${result.model}（${result.elapsedMs} ms）`);
    } catch (cause) {
      setError(handleApiError(cause, {
        CHAT_NOT_CONFIGURED: "默认模型没有配置密钥，请选择自定义模型。",
        CHAT_UNREACHABLE: "后端无法连接到模型地址，请检查地址和网络。",
        CHAT_TIMEOUT: "模型响应超时，请稍后重试。",
        CHAT_AUTH_FAILED: "模型拒绝认证，请检查密钥。",
        CHAT_UPSTREAM_ERROR: "模型服务返回错误，请检查地址和模型名。",
        REQUEST_INVALID: "模型地址须为 HTTP(S) 的 Chat Completions 接口。",
      }));
    } finally { setBusy(false); }
  }

  return <div className="mx-auto max-w-4xl space-y-5">
    <header><h1 className="text-2xl font-semibold">智能体模型设置</h1><p className="mt-2 text-sm text-foreground-500">配置用于数据分析的语言模型。RiskGNN+ 的训练和测试在模型工作台中进行。</p></header>
    <section className={`${panel} space-y-4`}>
      <label className="flex items-center gap-2 text-sm"><input type="radio" name="model-source" checked={!config.custom} onChange={() => { config.setCustom(false); setStatus(""); }} />使用后端默认模型 {config.defaults ? `· ${config.defaults.model}${config.defaults.keyConfigured ? "" : "（未配置密钥）"}` : config.loading ? "· 正在读取…" : "· 读取失败"}</label>
      <label className="flex items-center gap-2 text-sm"><input type="radio" name="model-source" checked={config.custom} onChange={() => { config.setCustom(true); setStatus(""); }} />自定义兼容 Chat Completions 的模型</label>
      <button type="button" className="rounded-md border border-background-300 px-3 py-1.5 text-xs" onClick={() => { config.useOpenLux(); setStatus(""); }}>预填 OpenLux · Qwen3.6-35B-A3B</button>
      {config.custom && <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-sm sm:col-span-2">接口地址<input className={input} value={config.url} placeholder="https://host/v1/chat/completions" onChange={(event) => { config.setUrl(event.target.value); setStatus(""); }} /></label>
        <label className="text-sm">模型名<input className={input} value={config.model} placeholder="模型 ID" onChange={(event) => { config.setModel(event.target.value); setStatus(""); }} /></label>
        <label className="text-sm">API 密钥（无认证可留空）<input className={input} type="password" autoComplete="off" value={config.apiKey} onChange={(event) => { config.setApiKey(event.target.value); setStatus(""); }} /></label>
      </div>}
      <div className="flex flex-wrap items-center gap-3">
        {config.custom && <button type="button" className="rounded-md border border-background-300 px-4 py-2 text-sm" disabled={!config.url.trim() || !config.model.trim()} onClick={() => { config.save(); setStatus("地址和模型名已保存在此浏览器。密钥只在本次登录页面中保留。"); }}>保存地址和模型名</button>}
        <button type="button" className={button} disabled={busy || (!config.custom && !config.defaults) || (config.custom && (!config.url.trim() || !config.model.trim()))} onClick={() => void test()}>{busy ? "测试中…" : "测试连接"}</button>
        {status && <span role="status" className="text-sm text-foreground-500">{status}</span>}
      </div>
      {error && <p role="alert" className="text-sm text-red-500">{error}</p>}
      <p className="text-xs text-foreground-500">自定义密钥只保留在本次登录的页面内存中，刷新后需重新输入。数据准备的字段统计和常见值会发送到所选模型地址。</p>
    </section>
    <Link className="text-sm text-primary-400 underline" to="/data-prep">返回数据准备</Link>
  </div>;
}
